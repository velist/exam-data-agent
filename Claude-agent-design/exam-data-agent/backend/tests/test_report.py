import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import services.report as report
from services.report import calc_change_rate, parse_pct, get_week_range


def test_calc_change_rate_normal():
    assert calc_change_rate(110, 100) == "+10.00%"

def test_calc_change_rate_decrease():
    assert calc_change_rate(90, 100) == "-10.00%"

def test_calc_change_rate_zero_base():
    assert calc_change_rate(100, 0) == "N/A"

def test_calc_change_rate_none_base():
    assert calc_change_rate(100, None) == "N/A"

def test_parse_pct_with_percent():
    assert parse_pct("12.34%") == 12.34

def test_parse_pct_number():
    assert parse_pct("56.78") == 56.78

def test_parse_pct_none():
    assert parse_pct(None) is None

def test_get_week_range():
    start, end = get_week_range("2026-03-27")
    assert start == "2026-03-21"
    assert end == "2026-03-27"

def test_get_week_range_midweek():
    start, end = get_week_range("2026-03-25")
    assert start == "2026-03-21"
    assert end == "2026-03-27"


def test_get_weekly_report_uses_operation_report_avg_quiz_count_for_behavior_and_growth(monkeypatch):
    def fake_query_cached(table_name, filters=None, order_by=None, order_desc=True, limit=None):
        if table_name == "dws_active_user_report_week":
            return {
                "columns": ["start_dt", "end_dt", "reg_users", "reg_users_yoy", "active_users", "active_users_yoy", "valid_active_users", "valid_active_users_yoy"],
                "rows": [["2026-03-29", "2026-04-04", "700", "650", "7000", "6800", "5000", "4900"]],
            }
        if table_name == "dws_pay_user_report_week":
            return {
                "columns": ["start_dt", "end_dt", "pay_users", "pay_users_yoy", "pay_conv_rate", "pay_conv_rate_yoy", "repurchase_rate", "repurchase_rate_yoy", "arpu", "arpu_yoy"],
                "rows": [["2026-03-29", "2026-04-04", "100", "95", "1.5", "1.4", "20", "18", "50", "48"]],
            }
        if table_name == "dws_retention_user_report_week":
            return {
                "columns": ["start_dt", "end_dt", "n1_ret_rate", "n1_ret_rate_yoy", "w_ret_rate", "w_ret_rate_yoy"],
                "rows": [["2026-03-29", "2026-04-04", "30", "28", "60", "58"]],
            }
        if table_name == "dws_user_behavior_report_week":
            return {
                "columns": [
                    "start_dt", "end_dt",
                    "quiz_part_rate", "quiz_part_rate_yoy",
                    "mock_part_rate", "mock_part_rate_yoy",
                    "course_part_rate", "course_part_rate_yoy",
                    "avg_play_progress", "avg_play_progress_yoy",
                    "quiz_rate", "quiz_rate_yoy",
                ],
                "rows": [["2026-03-29", "2026-04-04", "80", "78", "5", "4", "20", "19", "50", "49", "18.78", "17.00"]],
            }
        if table_name == "dws_user_daily_quiz_stats_day":
            return {
                "columns": ["stat_date", "daily_register_count", "daily_active_count", "daily_avg_exam"],
                "rows": [
                    ["2026-03-29", "100", "1000", "80.00"],
                    ["2026-03-30", "110", "1100", "81.00"],
                    ["2026-03-31", "120", "1200", "82.00"],
                    ["2026-04-01", "130", "1300", "83.00"],
                    ["2026-04-02", "140", "1400", "84.00"],
                    ["2026-04-03", "150", "1500", "85.00"],
                    ["2026-04-04", "160", "1600", "86.00"],
                ],
            }
        if table_name == "dws_operation_report_user_day":
            return {
                "columns": [
                    "start_date", "end_date", "avg_quiz_count", "week_avg_quiz_count",
                    "last_week_avg_quiz_count", "quiz_count_week_growth", "quiz_count_week_yoy",
                ],
                "rows": [["2026-04-04", "2026-04-04", "100.82", "100.82", "89.93", "12.11%", "-4.22%"]],
            }
        raise AssertionError(f"unexpected table: {table_name}")

    monkeypatch.setattr(report, "query_cached", fake_query_cached)

    result = report.get_weekly_report("2026-04-04")

    behavior_metric = result["sections"]["behavior"]["metrics"]["quiz_rate"]
    growth_metric = result["sections"]["user_growth"]["metrics"]["daily_avg_exam"]
    assert behavior_metric["value"] == "100.82"
    assert behavior_metric["wow"] == "+12.11%"
    assert behavior_metric["yoy"] == "-4.22%"
    assert growth_metric["value"] == "100.82"


def test_get_range_report_uses_operation_report_avg_quiz_count_for_growth(monkeypatch):
    monkeypatch.setattr(report, "_validate_range", lambda start, end: (report._parse_date(start), report._parse_date(end)))
    monkeypatch.setattr(report, "_get_intersected_weeks", lambda start, end: [["2026-03-29", "2026-04-04"]])
    monkeypatch.setattr(report, "_aggregate_reports", lambda period, weekly_reports, prev_reports=None: {
        "period": period,
        "sections": {
            "active": {
                "metrics": {
                    "reg_users": {"label": "注册用户", "value": "700", "wow": "+1.00%", "yoy": "+2.00%"},
                    "active_users": {"label": "活跃用户", "value": "7000", "wow": "+3.00%", "yoy": "+4.00%"},
                }
            },
            "behavior": {
                "metrics": {
                    "quiz_rate": {"label": "人均刷题量", "value": "100.82", "wow": "+12.11%", "yoy": "-4.22%"}
                }
            },
        },
        "weekly_reports": weekly_reports,
    })
    monkeypatch.setattr(report, "get_weekly_report", lambda end_date: {
        "period": {"start": "2026-03-29", "end": "2026-04-04"},
        "sections": {
            "behavior": {"metrics": {"quiz_rate": {"label": "人均刷题量", "value": "100.82", "wow": "+12.11%", "yoy": "-4.22%"}}}
        },
    })

    def fake_query_cached(table_name, filters=None, order_by=None, order_desc=True, limit=None):
        if table_name == "dws_operation_report_user_day":
            return {
                "columns": ["start_date", "end_date", "avg_quiz_count"],
                "rows": [
                    ["2026-03-29", "2026-03-29", "95.00"],
                    ["2026-03-30", "2026-03-30", "96.00"],
                    ["2026-03-31", "2026-03-31", "97.00"],
                    ["2026-04-01", "2026-04-01", "98.00"],
                    ["2026-04-02", "2026-04-02", "99.00"],
                    ["2026-04-03", "2026-04-03", "100.00"],
                    ["2026-04-04", "2026-04-04", "101.00"],
                ],
            }
        if table_name == "dws_user_daily_quiz_stats_day":
            return {
                "columns": ["stat_date", "daily_register_count", "daily_active_count", "daily_avg_exam"],
                "rows": [
                    ["2026-03-29", "100", "1000", "80.00"],
                    ["2026-03-30", "110", "1100", "81.00"],
                    ["2026-03-31", "120", "1200", "82.00"],
                    ["2026-04-01", "130", "1300", "83.00"],
                    ["2026-04-02", "140", "1400", "84.00"],
                    ["2026-04-03", "150", "1500", "85.00"],
                    ["2026-04-04", "160", "1600", "86.00"],
                ],
            }
        return {"columns": [], "rows": []}

    monkeypatch.setattr(report, "query_cached", fake_query_cached)

    result = report.get_range_report("2026-03-29", "2026-04-04")

    growth_metric = result["sections"]["user_growth"]["metrics"]["daily_avg_exam"]
    assert growth_metric["value"] == 98.0
    assert growth_metric["wow"] == "N/A"
    assert growth_metric["yoy"] == "N/A"
