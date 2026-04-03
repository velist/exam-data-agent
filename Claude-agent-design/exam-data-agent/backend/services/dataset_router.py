"""
聊天意图快速路由器。

在 NL2SQL 之前拦截高频问题，直接从 dataset_cache 或 report_cache
返回预生成数据，跳过 LLM 调用和 DB 查询。

路由未命中时返回 None，由调用方回退到原有 NL2SQL 链路。
"""

import logging
import re
from datetime import date, datetime, timedelta

logger = logging.getLogger("dataset_router")


# ---------------------------------------------------------------------------
# 时间提取
# ---------------------------------------------------------------------------

def _extract_month(message: str) -> str | None:
    """从消息中提取月份，返回 'YYYY-MM' 或 None。"""
    today = date.today()

    if "上月" in message or "上个月" in message:
        first = today.replace(day=1)
        prev = first - timedelta(days=1)
        return prev.strftime("%Y-%m")

    if "本月" in message or "这个月" in message or "当月" in message:
        return today.strftime("%Y-%m")

    # "3月" / "03月" / "12月"
    m = re.search(r"(\d{1,2})月", message)
    if m:
        month = int(m.group(1))
        if 1 <= month <= 12:
            year = today.year
            # 如果提到的月份大于当前月，可能指去年
            if month > today.month:
                year -= 1
            return f"{year}-{month:02d}"

    # "2026-03" 格式
    m = re.search(r"(\d{4})-(\d{2})", message)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    return None


def _extract_limit(message: str) -> int:
    """从消息中提取 '最近N周' 等数量，默认 4。"""
    m = re.search(r"最近\s*(\d+)\s*周", message)
    if m:
        return min(int(m.group(1)), 12)
    m = re.search(r"近\s*(\d+)\s*周", message)
    if m:
        return min(int(m.group(1)), 12)
    return 4


# ---------------------------------------------------------------------------
# 关键词匹配
# ---------------------------------------------------------------------------

_SALES_KW = {"销量", "销售额", "销售", "卖了", "成交", "赚了"}
_CLASS_KW = {"班次类型", "各班次", "题库", "课程", "私教"}
_CHANNEL_KW = {"渠道类型", "各渠道", "渠道", "合作商", "APP直充", "旗舰店", "客服销售"}
_SERIES_KW = {"系列", "各系列", "系列名称"}
_ACTIVE_KW = {"活跃用户", "活跃", "DAU", "有效活跃"}
_REGISTER_KW = {"注册用户", "注册", "新增用户", "拉新"}
_PAY_KW = {"付费", "转化率", "复购率", "ARPU", "付费用户"}
_RETENTION_KW = {"留存率", "次日留存", "周留存", "留存"}
_BEHAVIOR_KW = {"答题", "模考", "课程参与", "播放进度", "刷题量", "刷题"}
_CS_KW = {"客服", "投诉", "进线", "反馈", "退款", "退费", "工单"}
_OVERVIEW_KW = {"最近情况", "整体", "怎么样", "还行吗", "好不好", "异常", "概览", "关键指标"}


def _has_any(message: str, keywords: set) -> bool:
    return any(kw in message for kw in keywords)


# 包含这些关键词时，说明需要细粒度排名/明细，预生成数据集覆盖不了
_NEED_DETAIL_KW = {
    "最高", "最低", "最多", "最少", "排名", "排行", "TOP",
    "前5", "前10", "前3", "前五", "前十", "前三",
    "班次简称", "班次具体名称", "班次名称",
    "代理商名称", "代理商城市", "代理商",
    "哪个班次", "哪些班次", "哪个系列",
}


# ---------------------------------------------------------------------------
# 追问检测（复用 chat.py 的逻辑思路）
# ---------------------------------------------------------------------------

def _is_follow_up(message: str, history: list[dict]) -> bool:
    """追问场景较复杂，不走快速路由。"""
    if not history:
        return False
    normalized = message.strip()
    if not normalized:
        return False
    follow_up_markers = {"环比", "同比", "趋势呢", "它", "那个", "这个指标", "比一下", "只看", "其中"}
    if any(m in normalized for m in follow_up_markers):
        return True
    # 短消息 + 末尾"呢" → 大概率追问
    if len(normalized) <= 12 and normalized.endswith("呢"):
        return True
    return False


# ---------------------------------------------------------------------------
# 路由主函数
# ---------------------------------------------------------------------------

def try_route(message: str, history: list[dict]) -> dict | None:
    """
    尝试将用户消息路由到预生成数据集。

    返回 {"columns": [...], "rows": [...]} 或 None（回退 NL2SQL）。
    """
    # 追问不走快速路由
    if _is_follow_up(message, history):
        return None

    # 需要细粒度排名/明细的问题，预生成数据覆盖不了
    if _has_any(message, _NEED_DETAIL_KW):
        return None

    # --- 销售类 ---
    if _has_any(message, _SALES_KW):
        return _route_sales(message)

    # --- 用户类（report_cache 已有内存数据）---
    if _has_any(message, _ACTIVE_KW) or _has_any(message, _REGISTER_KW):
        return _route_user_active(message)

    if _has_any(message, _PAY_KW):
        return _route_report_table(message, "dws_pay_user_report_week",
                                   ["start_dt", "end_dt", "pay_users", "pay_conv_rate", "repurchase_rate", "arpu"])

    if _has_any(message, _RETENTION_KW):
        return _route_report_table(message, "dws_retention_user_report_week",
                                   ["start_dt", "end_dt", "n1_ret_rate", "w_ret_rate"])

    if _has_any(message, _BEHAVIOR_KW):
        return _route_report_table(message, "dws_user_behavior_report_week",
                                   ["start_dt", "end_dt", "quiz_part_rate", "mock_part_rate",
                                    "course_part_rate", "avg_play_progress", "quiz_rate"])

    # --- 客服类 ---
    if _has_any(message, _CS_KW):
        return _route_customer_service(message)

    # --- 综合概览 ---
    if _has_any(message, _OVERVIEW_KW):
        return _route_overview()

    return None


# ---------------------------------------------------------------------------
# 路由实现
# ---------------------------------------------------------------------------

def _route_sales(message: str) -> dict | None:
    from services.dataset_cache import get_dataset, filter_dataset

    month = _extract_month(message)

    # 按班次类型
    if _has_any(message, _CLASS_KW):
        if month:
            return filter_dataset("sales_monthly_by_class", "月份", month)
        return get_dataset("sales_monthly_by_class")

    # 按渠道类型
    if _has_any(message, _CHANNEL_KW):
        if month:
            return filter_dataset("sales_monthly_by_channel", "月份", month)
        return get_dataset("sales_monthly_by_channel")

    # 按系列
    if _has_any(message, _SERIES_KW):
        if month:
            return filter_dataset("sales_monthly_by_series", "月份", month)
        return get_dataset("sales_monthly_by_series")

    # 有明确月份 → 月度汇总
    if month:
        return filter_dataset("sales_monthly_total", "月份", month)

    # 泛销售问题 → 返回月度汇总全量
    return get_dataset("sales_monthly_total")


def _route_user_active(message: str) -> dict | None:
    """活跃/注册用户路由到 report_cache 中的内存数据。"""
    from services.report_cache import query_cached

    limit = _extract_limit(message)
    data = query_cached("dws_active_user_report_week",
                        order_by="end_dt", order_desc=True, limit=limit)
    if not data["columns"] or not data["rows"]:
        return None

    # 选择对外展示的列
    col_idx = {c: i for i, c in enumerate(data["columns"])}
    show_cols = ["start_dt", "end_dt", "reg_users", "active_users", "valid_active_users"]
    show_cols = [c for c in show_cols if c in col_idx]
    indices = [col_idx[c] for c in show_cols]

    rows = [[row[i] for i in indices] for row in reversed(data["rows"])]
    return {"columns": show_cols, "rows": rows}


def _route_report_table(message: str, table_name: str, show_cols: list[str]) -> dict | None:
    """通用周报表路由：从 report_cache 取最近 N 周数据。"""
    from services.report_cache import query_cached

    limit = _extract_limit(message)
    data = query_cached(table_name, order_by="end_dt", order_desc=True, limit=limit)
    if not data["columns"] or not data["rows"]:
        return None

    col_idx = {c: i for i, c in enumerate(data["columns"])}
    valid_cols = [c for c in show_cols if c in col_idx]
    indices = [col_idx[c] for c in valid_cols]

    rows = [[row[i] for i in indices] for row in reversed(data["rows"])]
    return {"columns": valid_cols, "rows": rows}


def _route_customer_service(message: str) -> dict | None:
    from services.dataset_cache import get_dataset

    if _has_any(message, _SERIES_KW) or "哪个系列" in message:
        return get_dataset("cs_by_series")

    return get_dataset("cs_by_theme")


def _route_overview() -> dict | None:
    """综合概览：最近 2 周核心指标。"""
    from services.report_cache import query_cached

    data = query_cached("dws_active_user_report_week",
                        order_by="end_dt", order_desc=True, limit=2)
    if not data["columns"] or not data["rows"]:
        return None

    col_idx = {c: i for i, c in enumerate(data["columns"])}
    show_cols = ["start_dt", "end_dt", "reg_users", "active_users", "valid_active_users"]
    show_cols = [c for c in show_cols if c in col_idx]
    indices = [col_idx[c] for c in show_cols]

    rows = [[row[i] for i in indices] for row in reversed(data["rows"])]
    return {"columns": show_cols, "rows": rows}
