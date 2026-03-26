import os
from datetime import datetime, timedelta
from db import execute_query

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'sql_templates')


def parse_pct(value) -> float | None:
    """将 '12.34%' 或 12.34 解析为浮点数"""
    if value is None or value == "" or value == "None":
        return None
    s = str(value).replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def calc_change_rate(current, previous) -> str:
    """计算环比/同比百分比变化"""
    if previous is None or previous == 0 or previous == "" or previous == "None":
        return "N/A"
    try:
        current_f = float(str(current).replace("%", ""))
        previous_f = float(str(previous).replace("%", ""))
    except (ValueError, TypeError):
        return "N/A"
    if previous_f == 0:
        return "N/A"
    rate = (current_f - previous_f) / previous_f * 100
    sign = "+" if rate >= 0 else ""
    return f"{sign}{rate:.2f}%"


def get_week_range(date_str: str) -> tuple[str, str]:
    """根据任意日期，返回所在业务周的(周六, 周五)。业务周：周六起始，周五结束。"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = dt.weekday()  # Monday=0, Sunday=6
    days_since_saturday = (weekday - 5) % 7
    saturday = dt - timedelta(days=days_since_saturday)
    friday = saturday + timedelta(days=6)
    return saturday.strftime("%Y-%m-%d"), friday.strftime("%Y-%m-%d")


def _load_template(name: str) -> str:
    path = os.path.join(TEMPLATES_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Remove SQL comment lines
    lines = [l for l in content.split("\n") if not l.strip().startswith("--")]
    return "\n".join(lines)


def _build_section(rows: list, columns: list, metrics_config: list[dict]) -> dict:
    """将查询结果构建为报告section结构。"""
    if not rows:
        return {"metrics": {}, "trend": []}

    col_idx = {c: i for i, c in enumerate(columns)}
    latest = rows[0]

    metrics = {}
    for mc in metrics_config:
        current_val = latest[col_idx[mc["col"]]]
        last_val = latest[col_idx[mc["last_col"]]] if mc.get("last_col") and mc["last_col"] in col_idx else None
        yoy_val = latest[col_idx[mc["yoy_col"]]] if mc.get("yoy_col") and mc["yoy_col"] in col_idx else None

        metrics[mc["key"]] = {
            "label": mc["label"],
            "value": current_val,
            "wow": calc_change_rate(current_val, last_val),
            "yoy": calc_change_rate(current_val, yoy_val),
        }

    trend = []
    start_idx = col_idx.get("start_dt", col_idx.get("stat_date"))
    end_idx = col_idx.get("end_dt")
    for row in reversed(rows):
        entry = {"start": row[start_idx] if start_idx is not None else ""}
        if end_idx is not None:
            entry["end"] = row[end_idx]
        for mc in metrics_config:
            entry[mc["key"]] = row[col_idx[mc["col"]]]
        trend.append(entry)

    return {"metrics": metrics, "trend": trend}


def get_weekly_report(date_str: str) -> dict:
    """获取周报数据。date_str为目标周内任意日期。"""
    start_date, end_date = get_week_range(date_str)
    result = {"period": {"start": start_date, "end": end_date}, "sections": {}}

    # 1. 活跃用户
    sql = _load_template("weekly_active.sql")
    data = execute_query(sql, {"end_date": end_date})
    result["sections"]["active"] = _build_section(data["rows"], data["columns"], [
        {"key": "reg_users", "label": "注册用户", "col": "reg_users", "last_col": "last_week_reg_users", "yoy_col": "reg_users_yoy"},
        {"key": "active_users", "label": "活跃用户", "col": "active_users", "last_col": "last_week_active_users", "yoy_col": "active_users_yoy"},
        {"key": "valid_active_users", "label": "有效活跃用户", "col": "valid_active_users", "last_col": "last_week_valid_active_users", "yoy_col": "valid_active_users_yoy"},
    ])

    # 2. 付费
    sql = _load_template("weekly_pay.sql")
    data = execute_query(sql, {"end_date": end_date})
    result["sections"]["pay"] = _build_section(data["rows"], data["columns"], [
        {"key": "pay_users", "label": "付费用户", "col": "pay_users", "last_col": "last_week_pay_users", "yoy_col": "pay_users_yoy"},
        {"key": "pay_conv_rate", "label": "付费转化率", "col": "pay_conv_rate", "last_col": "last_week_pay_conv_rate", "yoy_col": "pay_conv_rate_yoy"},
        {"key": "repurchase_rate", "label": "复购率", "col": "repurchase_rate", "last_col": "last_week_repurchase_rate", "yoy_col": "repurchase_rate_yoy"},
        {"key": "arpu", "label": "ARPU", "col": "arpu", "last_col": "last_week_arpu", "yoy_col": "arpu_yoy"},
    ])

    # 3. 留存
    sql = _load_template("weekly_retention.sql")
    data = execute_query(sql, {"end_date": end_date})
    result["sections"]["retention"] = _build_section(data["rows"], data["columns"], [
        {"key": "n1_ret_rate", "label": "次日留存率", "col": "n1_ret_rate", "last_col": "last_week_n1_ret_rate", "yoy_col": "n1_ret_rate_yoy"},
        {"key": "w_ret_rate", "label": "周留存率", "col": "w_ret_rate", "last_col": "last_week_w_ret_rate", "yoy_col": "w_ret_rate_yoy"},
    ])

    # 4. 行为
    sql = _load_template("weekly_behavior.sql")
    data = execute_query(sql, {"end_date": end_date})
    rows_reversed = list(reversed(data["rows"])) if data["rows"] else []
    result["sections"]["behavior"] = _build_section(rows_reversed, data["columns"], [
        {"key": "quiz_part_rate", "label": "答题参与率", "col": "quiz_part_rate", "last_col": "last_week_quiz_part_rate", "yoy_col": "quiz_part_rate_yoy"},
        {"key": "mock_part_rate", "label": "模考参与率", "col": "mock_part_rate", "last_col": "last_week_mock_part_rate", "yoy_col": "mock_part_rate_yoy"},
        {"key": "course_part_rate", "label": "课程参与率", "col": "course_part_rate", "last_col": "last_week_course_part_rate", "yoy_col": "course_part_rate_yoy"},
        {"key": "avg_play_progress", "label": "人均播放进度", "col": "avg_play_progress", "last_col": "last_week_avg_play_progress", "yoy_col": "avg_play_progress_yoy"},
        {"key": "quiz_rate", "label": "人均刷题量", "col": "quiz_rate", "last_col": "last_week_quiz_rate", "yoy_col": "quiz_rate_yoy"},
    ])

    # 5. 用户增长（日粒度）
    sql = _load_template("weekly_user_growth.sql")
    data = execute_query(sql, {"start_date": start_date, "end_date": end_date})
    if data["rows"]:
        col_idx = {c: i for i, c in enumerate(data["columns"])}
        last_row = data["rows"][-1]
        active_metrics = result["sections"].get("active", {}).get("metrics", {})
        result["sections"]["user_growth"] = {
            "metrics": {
                "daily_register": {"label": "本周日均注册", "value": last_row[col_idx.get("week_avg_register", 0)], "wow": active_metrics.get("reg_users", {}).get("wow", "N/A"), "yoy": active_metrics.get("reg_users", {}).get("yoy", "N/A")},
                "daily_active": {"label": "本周日均活跃", "value": last_row[col_idx.get("week_avg_active", 0)], "wow": active_metrics.get("active_users", {}).get("wow", "N/A"), "yoy": active_metrics.get("active_users", {}).get("yoy", "N/A")},
                "daily_avg_exam": {"label": "本周人均刷题", "value": last_row[col_idx.get("week_avg_exam", 0)], "wow": "N/A", "yoy": "N/A"},
            },
            "trend": [{"start": row[col_idx["stat_date"]], "daily_register": row[col_idx["daily_register_count"]], "daily_active": row[col_idx["daily_active_count"]]} for row in data["rows"]],
        }
    else:
        result["sections"]["user_growth"] = {"metrics": {}, "trend": []}

    return result


def get_monthly_report(month_str: str) -> dict:
    """获取月报。month_str格式为 '2026-03'。按周起始日期归属月份。"""
    year, month = map(int, month_str.split("-"))

    sql = "SELECT DISTINCT start_dt, end_dt FROM dws.dws_active_user_report_week WHERE SUBSTRING(start_dt, 1, 7) = :month ORDER BY start_dt"
    data = execute_query(sql, {"month": month_str})

    if not data["rows"]:
        return {"period": {"month": month_str}, "sections": {}, "weekly_reports": []}

    weekly_reports = []
    for row in data["rows"]:
        wr = get_weekly_report(row[1])
        weekly_reports.append(wr)

    # 月度汇总
    all_sections = {}
    for wr in weekly_reports:
        for section_key, section_data in wr.get("sections", {}).items():
            if "metrics" not in section_data:
                continue
            if section_key not in all_sections:
                all_sections[section_key] = {}
            for metric_key, metric in section_data["metrics"].items():
                if metric_key not in all_sections[section_key]:
                    all_sections[section_key][metric_key] = {"label": metric["label"], "values": []}
                all_sections[section_key][metric_key]["values"].append(metric["value"])

    sections = {}
    for section_key, metrics_map in all_sections.items():
        metrics = {}
        for metric_key, info in metrics_map.items():
            values = info["values"]
            try:
                nums = [float(str(v).replace("%", "").replace(",", "")) for v in values if v and v != "N/A"]
                avg_val = round(sum(nums) / len(nums), 2) if nums else "N/A"
            except (ValueError, TypeError):
                avg_val = values[-1] if values else "N/A"
            metrics[metric_key] = {"label": info["label"], "value": avg_val, "wow": "N/A", "yoy": "N/A"}

        trend = []
        for wr in weekly_reports:
            section_data = wr.get("sections", {}).get(section_key, {})
            entry = {"start": wr["period"]["start"], "end": wr["period"]["end"]}
            for mk in metrics:
                entry[mk] = section_data.get("metrics", {}).get(mk, {}).get("value", "N/A")
            trend.append(entry)
        sections[section_key] = {"metrics": metrics, "trend": trend}

    # 月环比（查询上月数据）
    prev_month_dt = datetime(year, month, 1) - timedelta(days=1)
    prev_month_str = prev_month_dt.strftime("%Y-%m")
    prev_sql = "SELECT DISTINCT start_dt, end_dt FROM dws.dws_active_user_report_week WHERE SUBSTRING(start_dt, 1, 7) = :month ORDER BY start_dt"
    prev_data = execute_query(prev_sql, {"month": prev_month_str})
    if prev_data["rows"]:
        prev_reports = [get_weekly_report(row[1]) for row in prev_data["rows"]]
        for section_key in sections:
            for metric_key in sections[section_key]["metrics"]:
                prev_values = []
                for pr in prev_reports:
                    v = pr.get("sections", {}).get(section_key, {}).get("metrics", {}).get(metric_key, {}).get("value")
                    if v:
                        prev_values.append(v)
                if prev_values:
                    try:
                        prev_nums = [float(str(v).replace("%", "").replace(",", "")) for v in prev_values]
                        prev_avg = sum(prev_nums) / len(prev_nums)
                        sections[section_key]["metrics"][metric_key]["wow"] = calc_change_rate(
                            sections[section_key]["metrics"][metric_key]["value"], prev_avg
                        )
                    except (ValueError, TypeError):
                        pass

    return {"period": {"month": month_str, "weeks": len(weekly_reports)}, "sections": sections, "weekly_reports": weekly_reports}
