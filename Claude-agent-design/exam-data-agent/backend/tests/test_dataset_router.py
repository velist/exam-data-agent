import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.dataset_router import (
    _extract_month,
    _extract_limit,
    _is_follow_up,
    _has_any,
    _SALES_KW, _CLASS_KW, _CHANNEL_KW, _ACTIVE_KW, _REGISTER_KW,
    _PAY_KW, _RETENTION_KW, _CS_KW, _OVERVIEW_KW, _NEED_DETAIL_KW,
    try_route,
)


# ---------------------------------------------------------------------------
# 时间提取
# ---------------------------------------------------------------------------

class TestExtractMonth:
    def test_explicit_month_number(self):
        # 假设当前 2026 年，4月之前的月份属于今年
        month = _extract_month("3月各班次类型销量")
        assert month is not None
        assert month.endswith("-03")

    def test_last_month(self):
        month = _extract_month("上月销售额")
        assert month is not None

    def test_this_month(self):
        month = _extract_month("本月销量")
        assert month is not None

    def test_yyyy_mm_format(self):
        assert _extract_month("2026-02的数据") == "2026-02"

    def test_no_month(self):
        assert _extract_month("最近情况怎么样") is None


class TestExtractLimit:
    def test_recent_n_weeks(self):
        assert _extract_limit("最近4周活跃用户趋势") == 4
        assert _extract_limit("最近8周") == 8

    def test_near_n_weeks(self):
        assert _extract_limit("近6周趋势") == 6

    def test_default(self):
        assert _extract_limit("最近活跃用户") == 4

    def test_cap_at_12(self):
        assert _extract_limit("最近100周") == 12


# ---------------------------------------------------------------------------
# 关键词匹配
# ---------------------------------------------------------------------------

class TestKeywordMatching:
    def test_sales_keywords(self):
        assert _has_any("3月各班次类型销量和销售额", _SALES_KW)
        assert _has_any("上月卖了多少", _SALES_KW)
        assert not _has_any("最近活跃用户", _SALES_KW)

    def test_class_keywords(self):
        assert _has_any("各班次类型销量", _CLASS_KW)
        assert _has_any("题库销量", _CLASS_KW)

    def test_channel_keywords(self):
        assert _has_any("各渠道类型销售额", _CHANNEL_KW)
        assert _has_any("APP直充销量", _CHANNEL_KW)

    def test_active_keywords(self):
        assert _has_any("最近4周活跃用户趋势", _ACTIVE_KW)
        assert _has_any("DAU多少", _ACTIVE_KW)

    def test_register_keywords(self):
        assert _has_any("上周注册用户多少", _REGISTER_KW)
        assert _has_any("拉新做得咋样", _REGISTER_KW)

    def test_pay_keywords(self):
        assert _has_any("付费转化率", _PAY_KW)
        assert _has_any("ARPU多少", _PAY_KW)

    def test_retention_keywords(self):
        assert _has_any("最近留存率", _RETENTION_KW)
        assert _has_any("次日留存", _RETENTION_KW)

    def test_cs_keywords(self):
        assert _has_any("最近客服进线情况", _CS_KW)
        assert _has_any("退款有多少", _CS_KW)

    def test_overview_keywords(self):
        assert _has_any("最近情况怎么样", _OVERVIEW_KW)
        assert _has_any("有什么异常", _OVERVIEW_KW)


# ---------------------------------------------------------------------------
# 追问检测
# ---------------------------------------------------------------------------

class TestFollowUp:
    def test_no_history_not_follow_up(self):
        assert not _is_follow_up("环比呢", [])

    def test_with_history_and_marker(self):
        history = [{"role": "user", "content": "上周注册用户"}]
        assert _is_follow_up("环比呢", history)
        assert _is_follow_up("同比呢", history)
        assert _is_follow_up("它怎么样", history)

    def test_short_ne_question(self):
        history = [{"role": "user", "content": "3月销售额"}]
        assert _is_follow_up("退款类呢", history)

    def test_long_new_question_not_follow_up(self):
        history = [{"role": "user", "content": "上周注册用户"}]
        assert not _is_follow_up("3月各班次类型销量和销售额", history)


# ---------------------------------------------------------------------------
# 路由主函数（用 mock 数据）
# ---------------------------------------------------------------------------

class TestTryRoute:
    def test_follow_up_returns_none(self):
        history = [{"role": "user", "content": "上周注册用户"}]
        assert try_route("环比呢", history) is None

    def test_sales_by_class_routes(self, monkeypatch):
        fake = {"columns": ["月份", "班次类型", "销量", "销售额"], "rows": [["2026-03", "题库", "300", "8000"]]}
        monkeypatch.setattr("services.dataset_cache.get_dataset", lambda name: fake)
        monkeypatch.setattr("services.dataset_cache.filter_dataset", lambda name, col, val: fake)

        result = try_route("3月各班次类型销量和销售额", [])
        assert result is not None
        assert result["columns"] == fake["columns"]

    def test_active_users_routes(self, monkeypatch):
        fake = {
            "columns": ["start_dt", "end_dt", "reg_users", "active_users", "valid_active_users"],
            "rows": [["2026-03-22", "2026-03-28", "1000", "5000", "3000"]],
        }
        monkeypatch.setattr("services.report_cache.query_cached", lambda *a, **kw: fake)

        result = try_route("最近4周活跃用户趋势", [])
        assert result is not None
        assert "active_users" in result["columns"]

    def test_cs_routes(self, monkeypatch):
        fake = {"columns": ["月份", "问题主题", "数量"], "rows": [["2026-03", "退款类", "50"]]}
        monkeypatch.setattr("services.dataset_cache.get_dataset", lambda name: fake)

        result = try_route("最近客服进线情况", [])
        assert result is not None

    def test_unmatched_returns_none(self):
        # 不匹配任何关键词的随机问题
        assert try_route("北京天气怎么样", []) is None

    def test_detail_query_falls_through(self):
        """需要细粒度排名/明细的问题不走路由"""
        assert try_route("3月销量最高的班次简称", []) is None
        assert try_route("APP直充渠道2月销量最高的前5个班次简称", []) is None
        assert try_route("哪个班次卖得最多", []) is None
        assert try_route("各代理商销售额排名", []) is None

    def test_overview_routes(self, monkeypatch):
        fake = {
            "columns": ["start_dt", "end_dt", "reg_users", "active_users", "valid_active_users"],
            "rows": [
                ["2026-03-22", "2026-03-28", "1000", "5000", "3000"],
                ["2026-03-15", "2026-03-21", "900", "4800", "2900"],
            ],
        }
        monkeypatch.setattr("services.report_cache.query_cached", lambda *a, **kw: fake)

        result = try_route("最近情况怎么样", [])
        assert result is not None
        assert len(result["rows"]) == 2
