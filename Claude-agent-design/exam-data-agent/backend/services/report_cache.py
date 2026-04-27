"""
报告数据本地缓存。启动时从磁盘读缓存（秒级），然后后台线程从远程 DB 刷新。
report.py 不再直接查库，而是通过 query_cached() 从内存读数据。
"""

import os
import json
import logging
import threading
from db import execute_query

logger = logging.getLogger("report_cache")

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CACHE_FILE = os.path.join(CACHE_DIR, "report_cache.json")

# 需要缓存的表及其全量查询
TABLES = {
    "dws_active_user_report_week": "SELECT * FROM dws.dws_active_user_report_week ORDER BY end_dt DESC",
    "dws_pay_user_report_week": "SELECT * FROM dws.dws_pay_user_report_week ORDER BY end_dt DESC",
    "dws_retention_user_report_week": "SELECT * FROM dws.dws_retention_user_report_week ORDER BY end_dt DESC",
    "dws_user_behavior_report_week": "SELECT * FROM dws.dws_user_behavior_report_week ORDER BY end_dt DESC",
    "dws_user_daily_quiz_stats_day": "SELECT * FROM dws.dws_user_daily_quiz_stats_day ORDER BY stat_date DESC",
    "dws_operation_report_user_day": "SELECT * FROM dws.dws_operation_report_user_day ORDER BY end_date DESC",
}

_cache: dict[str, dict] = {}
_ready = threading.Event()


def _load_from_disk() -> bool:
    """从磁盘 JSON 加载缓存，成功返回 True"""
    if not os.path.exists(CACHE_FILE):
        return False
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _cache.update(data)
        logger.info(f"从磁盘加载缓存成功，共 {len(data)} 张表")
        return True
    except Exception as e:
        logger.warning(f"磁盘缓存读取失败: {e}")
        return False


def _save_to_disk():
    """把内存缓存写到磁盘"""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)
        logger.info("缓存已写入磁盘")
    except Exception as e:
        logger.warning(f"缓存写入磁盘失败: {e}")


def _refresh_from_db():
    """从远程 DB 全量拉取数据"""
    for table_name, sql in TABLES.items():
        try:
            data = execute_query(sql)
            _cache[table_name] = data
            logger.info(f"刷新 {table_name}: {len(data['rows'])} 行")
        except Exception as e:
            logger.error(f"刷新 {table_name} 失败: {e}")
    _save_to_disk()


def init_cache():
    """启动时调用：先读磁盘缓存（秒级就绪），然后后台刷新远程数据"""
    disk_ok = _load_from_disk()
    if disk_ok:
        _ready.set()
        logger.info("磁盘缓存已就绪，后台异步刷新远程数据")
        thread = threading.Thread(target=_background_refresh, daemon=True)
        thread.start()
    else:
        logger.info("无磁盘缓存，同步从远程加载...")
        _refresh_from_db()
        _ready.set()
        logger.info("远程数据加载完成")


def _background_refresh():
    """后台刷新"""
    try:
        _refresh_from_db()
        logger.info("后台刷新完成")
    except Exception as e:
        logger.error(f"后台刷新失败: {e}")


def get_cached_table(table_name: str) -> dict:
    """获取缓存的表数据。返回 {"columns": [...], "rows": [...]}"""
    _ready.wait(timeout=60)
    return _cache.get(table_name, {"columns": [], "rows": []})


def query_cached(table_name: str, filters: dict | None = None,
                 order_by: str | None = None, order_desc: bool = True,
                 limit: int | None = None) -> dict:
    """
    从缓存中查询数据，模拟简单的 WHERE + ORDER BY + LIMIT。
    filters: {col_name: {"op": "<="|">="|"=="|"between", "value": ...}}
    """
    data = get_cached_table(table_name)
    if not data["columns"] or not data["rows"]:
        return {"columns": [], "rows": []}

    col_idx = {c: i for i, c in enumerate(data["columns"])}
    rows = list(data["rows"])

    # 过滤
    if filters:
        filtered = []
        for row in rows:
            match = True
            for col, cond in filters.items():
                if col not in col_idx:
                    match = False
                    break
                val = row[col_idx[col]]
                op = cond.get("op", "==")
                target = cond["value"]
                if op == "<=":
                    match = match and (str(val) <= str(target))
                elif op == ">=":
                    match = match and (str(val) >= str(target))
                elif op == "==":
                    match = match and (str(val) == str(target))
                elif op == "between":
                    match = match and (str(target[0]) <= str(val) <= str(target[1]))
            if match:
                filtered.append(row)
        rows = filtered

    # 排序
    if order_by and order_by in col_idx:
        idx = col_idx[order_by]
        rows.sort(key=lambda r: str(r[idx]), reverse=order_desc)

    # 限制
    if limit:
        rows = rows[:limit]

    return {"columns": data["columns"], "rows": rows}
