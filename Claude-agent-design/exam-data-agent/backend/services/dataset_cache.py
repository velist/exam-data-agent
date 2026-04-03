"""
业务数据集预聚合缓存。

与 report_cache（全量缓存 5 张 dws 周报表）互补，
本模块预跑销售 / 客服等高频聚合查询，结果驻内存 + 磁盘持久化。

启动时先从磁盘读取（秒级就绪），再后台线程从远程 DB 刷新。
聊天路由器 (dataset_router) 会优先从这里取数据，跳过 NL2SQL + DB。
"""

import json
import logging
import os
import threading
import time

from db import execute_query

logger = logging.getLogger("dataset_cache")

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CACHE_FILE = os.path.join(CACHE_DIR, "dataset_cache.json")

REFRESH_INTERVAL = 6 * 3600  # 每 6 小时刷新

# ---------------------------------------------------------------------------
# 预聚合 SQL 定义
# ---------------------------------------------------------------------------

# 渠道类型映射（视图已有渠道类型字段，直接使用）
DATASETS = {
    # 销售：按月汇总
    "sales_monthly_total": """
        SELECT SUBSTRING(销售日期,1,7) AS 月份,
               COUNT(*) AS 销量,
               ROUND(SUM(销售金额),2) AS 销售额
        FROM dws.dws_v_salesflow_dateil
        WHERE 销售日期 >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY 月份
        ORDER BY 月份
    """,

    # 销售：按月 + 班次类型
    "sales_monthly_by_class": """
        SELECT SUBSTRING(销售日期,1,7) AS 月份,
               班次类型,
               COUNT(*) AS 销量,
               ROUND(SUM(销售金额),2) AS 销售额
        FROM dws.dws_v_salesflow_dateil
        WHERE 销售日期 >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY 月份, 班次类型
        ORDER BY 月份, 销售额 DESC
    """,

    # 销售：按月 + 渠道类型
    "sales_monthly_by_channel": """
        SELECT SUBSTRING(销售日期,1,7) AS 月份,
               渠道类型,
               COUNT(*) AS 销量,
               ROUND(SUM(销售金额),2) AS 销售额
        FROM dws.dws_v_salesflow_dateil
        WHERE 销售日期 >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY 月份, 渠道类型
        ORDER BY 月份, 销售额 DESC
    """,

    # 销售：按月 + 系列名称
    "sales_monthly_by_series": """
        SELECT SUBSTRING(销售日期,1,7) AS 月份,
               系列名称,
               COUNT(*) AS 销量,
               ROUND(SUM(销售金额),2) AS 销售额
        FROM dws.dws_v_salesflow_dateil
        WHERE 销售日期 >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY 月份, 系列名称
        ORDER BY 月份, 销售额 DESC
    """,

    # 客服：按问题主题聚合（最近 90 天）
    "cs_by_theme": """
        SELECT DATE_FORMAT(submit_time, '%Y-%m') AS 月份,
               question_theme AS 问题主题,
               COUNT(*) AS 数量
        FROM dws.dws_customer_service
        WHERE submit_time >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
        GROUP BY 月份, 问题主题
        ORDER BY 月份, 数量 DESC
    """,

    # 客服：按系列聚合（最近 90 天）
    "cs_by_series": """
        SELECT series_name AS 系列,
               COUNT(*) AS 进线量
        FROM dws.dws_customer_service
        WHERE submit_time >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
        GROUP BY 系列
        ORDER BY 进线量 DESC
    """,
}

# ---------------------------------------------------------------------------
# 内存缓存
# ---------------------------------------------------------------------------

_cache: dict[str, dict] = {}
_ready = threading.Event()
_refresh_timer: threading.Timer | None = None


# ---------------------------------------------------------------------------
# 磁盘 IO
# ---------------------------------------------------------------------------

def _load_from_disk() -> bool:
    if not os.path.exists(CACHE_FILE):
        return False
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _cache.update(data)
        logger.info("从磁盘加载数据集缓存成功，共 %d 个数据集", len(data))
        return True
    except Exception as e:
        logger.warning("磁盘数据集缓存读取失败: %s", e)
        return False


def _save_to_disk():
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)
        logger.info("数据集缓存已写入磁盘")
    except Exception as e:
        logger.warning("数据集缓存写入磁盘失败: %s", e)


# ---------------------------------------------------------------------------
# DB 刷新
# ---------------------------------------------------------------------------

def _refresh_from_db():
    for name, sql in DATASETS.items():
        try:
            data = execute_query(sql)
            _cache[name] = data
            logger.info("刷新数据集 %s: %d 行", name, len(data["rows"]))
        except Exception as e:
            logger.error("刷新数据集 %s 失败: %s", name, e)
    _cache["_ts"] = {"columns": [], "rows": [], "refreshed_at": time.time()}
    _save_to_disk()


def _background_refresh():
    try:
        _refresh_from_db()
        logger.info("后台数据集刷新完成")
    except Exception as e:
        logger.error("后台数据集刷新失败: %s", e)
    _schedule_next_refresh()


def _schedule_next_refresh():
    global _refresh_timer
    _refresh_timer = threading.Timer(REFRESH_INTERVAL, _background_refresh)
    _refresh_timer.daemon = True
    _refresh_timer.start()


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------

def init_dataset_cache():
    """启动时调用：先读磁盘（秒级就绪），再后台从 DB 刷新。"""
    disk_ok = _load_from_disk()
    if disk_ok:
        _ready.set()
        logger.info("磁盘数据集缓存已就绪，后台异步刷新")
        thread = threading.Thread(target=_background_refresh, daemon=True)
        thread.start()
    else:
        logger.info("无磁盘数据集缓存，同步从远程加载...")
        _refresh_from_db()
        _ready.set()
        _schedule_next_refresh()
        logger.info("数据集远程加载完成")


def get_dataset(name: str) -> dict:
    """获取预生成数据集。返回 {"columns": [...], "rows": [...]}"""
    _ready.wait(timeout=60)
    return _cache.get(name, {"columns": [], "rows": []})


def filter_dataset(name: str, col_name: str, value: str) -> dict:
    """按某一列精确过滤数据集。"""
    data = get_dataset(name)
    if not data["columns"] or not data["rows"]:
        return {"columns": [], "rows": []}

    col_idx = {c: i for i, c in enumerate(data["columns"])}
    if col_name not in col_idx:
        return data  # 列不存在则返回全部

    idx = col_idx[col_name]
    filtered = [row for row in data["rows"] if row[idx] == value]
    return {"columns": data["columns"], "rows": filtered}
