import os
from datetime import datetime, timedelta
from services.report_cache import query_cached

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'sql_templates')


def parse_pct(value) -> float | None:
    if value is None or value == "" or value == "None":
        return None
    s = str(value).replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def calc_change_rate(current, previous) -> str:
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
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = dt.weekday()
    days_since_saturday = (weekday - 5) % 7
    saturday = dt - timedelta(days=days_since_saturday)
    friday = saturday + timedelta(days=6)
    return saturday.strftime("%Y-%m-%d"), friday.strftime("%Y-%m-%d")


def _query_weekly_table(table_name: str, end_date: str, metric_cols: list[str], yoy_cols: list[str]) -> dict:
    """
    从缓存查周报表数据，模拟 SQL 模板的 WHERE end_dt <= :end_date + LEAD 窗口函数。
    返回 {"columns": [...], "rows": [...]}，其中 columns 包含原始列 + last_week_xxx 计算列。
    """
    data = query_cached(table_name, filters={"end_dt": {"op": "<=", "value": end_date}},
                        order_by="end_dt", order_desc=True, limit=9)
    if not data["columns"] or not data["rows"]:
        return {"columns": [], "rows": []}

    src_cols = data["columns"]
    src_idx = {c: i for i, c in enumerate(src_cols)}

    # 构建输出列：start_dt, end_dt, 每个 metric 的 (value, last_week, yoy)
    out_cols = ["start_dt", "end_dt"]
    for mc, yc in zip(metric_cols, yoy_cols):
        last_col = f"last_week_{mc}"
        out_cols.extend([mc, last_col, yc])

    out_rows = []
    rows = data["rows"]
    for i, row in enumerate(rows):
        if i >= 8:
            break
        out_row = [row[src_idx["start_dt"]], row[src_idx["end_dt"]]]
        for mc, yc in zip(metric_cols, yoy_cols):
            val = row[src_idx[mc]] if mc in src_idx else ""
            # LEAD(1) on DESC order = next row = rows[i+1]
            last_val = rows[i + 1][src_idx[mc]] if (i + 1 < len(rows) and mc in src_idx) else ""
            yoy_val = row[src_idx[yc]] if yc in src_idx else ""
            out_row.extend([val, last_val, yoy_val])
        out_rows.append(out_row)

    return {"columns": out_cols, "rows": out_rows}


def _build_section(rows: list, columns: list, metrics_config: list[dict]) -> dict:
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


def _format_pct_change(value) -> str:
    parsed = parse_pct(value)
    if parsed is None:
        return "N/A"
    sign = "+" if parsed >= 0 else ""
    return f"{sign}{parsed:.2f}%"


def _get_latest_operation_quiz_summary(end_date: str) -> dict | None:
    data = query_cached(
        "dws_operation_report_user_day",
        filters={"end_date": {"op": "<=", "value": end_date}},
        order_by="end_date",
        order_desc=True,
        limit=1,
    )
    if not data["rows"]:
        return None
    col_idx = {c: i for i, c in enumerate(data["columns"])}
    row = data["rows"][0]
    return {col: row[idx] for col, idx in col_idx.items()}


def _get_operation_quiz_rows(start_date: str, end_date: str) -> list[dict]:
    data = query_cached(
        "dws_operation_report_user_day",
        filters={"end_date": {"op": "between", "value": [start_date, end_date]}},
        order_by="end_date",
        order_desc=False,
    )
    if not data["rows"]:
        return []
    col_idx = {c: i for i, c in enumerate(data["columns"])}
    return [{col: row[idx] for col, idx in col_idx.items()} for row in data["rows"]]


def get_weekly_report(date_str: str) -> dict:
    start_date, end_date = get_week_range(date_str)
    result = {"period": {"start": start_date, "end": end_date}, "sections": {}}

    # 1. 活跃用户
    data = _query_weekly_table(
        "dws_active_user_report_week", end_date,
        ["reg_users", "active_users", "valid_active_users"],
        ["reg_users_yoy", "active_users_yoy", "valid_active_users_yoy"],
    )
    result["sections"]["active"] = _build_section(data["rows"], data["columns"], [
        {"key": "reg_users", "label": "注册用户", "col": "reg_users", "last_col": "last_week_reg_users", "yoy_col": "reg_users_yoy"},
        {"key": "active_users", "label": "活跃用户", "col": "active_users", "last_col": "last_week_active_users", "yoy_col": "active_users_yoy"},
        {"key": "valid_active_users", "label": "有效活跃用户", "col": "valid_active_users", "last_col": "last_week_valid_active_users", "yoy_col": "valid_active_users_yoy"},
    ])

    # 2. 付费
    data = _query_weekly_table(
        "dws_pay_user_report_week", end_date,
        ["pay_users", "pay_conv_rate", "repurchase_rate", "arpu"],
        ["pay_users_yoy", "pay_conv_rate_yoy", "repurchase_rate_yoy", "arpu_yoy"],
    )
    result["sections"]["pay"] = _build_section(data["rows"], data["columns"], [
        {"key": "pay_users", "label": "付费用户", "col": "pay_users", "last_col": "last_week_pay_users", "yoy_col": "pay_users_yoy"},
        {"key": "pay_conv_rate", "label": "付费转化率", "col": "pay_conv_rate", "last_col": "last_week_pay_conv_rate", "yoy_col": "pay_conv_rate_yoy"},
        {"key": "repurchase_rate", "label": "复购率", "col": "repurchase_rate", "last_col": "last_week_repurchase_rate", "yoy_col": "repurchase_rate_yoy"},
        {"key": "arpu", "label": "ARPU", "col": "arpu", "last_col": "last_week_arpu", "yoy_col": "arpu_yoy"},
    ])

    # 3. 留存
    data = _query_weekly_table(
        "dws_retention_user_report_week", end_date,
        ["n1_ret_rate", "w_ret_rate"],
        ["n1_ret_rate_yoy", "w_ret_rate_yoy"],
    )
    result["sections"]["retention"] = _build_section(data["rows"], data["columns"], [
        {"key": "n1_ret_rate", "label": "次日留存率", "col": "n1_ret_rate", "last_col": "last_week_n1_ret_rate", "yoy_col": "n1_ret_rate_yoy"},
        {"key": "w_ret_rate", "label": "周留存率", "col": "w_ret_rate", "last_col": "last_week_w_ret_rate", "yoy_col": "w_ret_rate_yoy"},
    ])

    # 4. 行为（原 SQL 用 LAG + ORDER ASC，等价于 LEAD + DESC 再 reverse）
    data = _query_weekly_table(
        "dws_user_behavior_report_week", end_date,
        ["quiz_part_rate", "mock_part_rate", "course_part_rate", "avg_play_progress", "quiz_rate"],
        ["quiz_part_rate_yoy", "mock_part_rate_yoy", "course_part_rate_yoy", "avg_play_progress_yoy", "quiz_rate_yoy"],
    )
    rows_reversed = list(reversed(data["rows"])) if data["rows"] else []
    result["sections"]["behavior"] = _build_section(rows_reversed, data["columns"], [
        {"key": "quiz_part_rate", "label": "答题参与率", "col": "quiz_part_rate", "last_col": "last_week_quiz_part_rate", "yoy_col": "quiz_part_rate_yoy"},
        {"key": "mock_part_rate", "label": "模考参与率", "col": "mock_part_rate", "last_col": "last_week_mock_part_rate", "yoy_col": "mock_part_rate_yoy"},
        {"key": "course_part_rate", "label": "课程参与率", "col": "course_part_rate", "last_col": "last_week_course_part_rate", "yoy_col": "course_part_rate_yoy"},
        {"key": "avg_play_progress", "label": "人均播放进度", "col": "avg_play_progress", "last_col": "last_week_avg_play_progress", "yoy_col": "avg_play_progress_yoy"},
        {"key": "quiz_rate", "label": "人均刷题量", "col": "quiz_rate", "last_col": "last_week_quiz_rate", "yoy_col": "quiz_rate_yoy"},
    ])
    operation_quiz_summary = _get_latest_operation_quiz_summary(end_date)
    if operation_quiz_summary:
        behavior_metrics = result["sections"].get("behavior", {}).get("metrics", {})
        if "quiz_rate" in behavior_metrics:
            behavior_metrics["quiz_rate"]["value"] = operation_quiz_summary.get("week_avg_quiz_count", behavior_metrics["quiz_rate"]["value"])
            behavior_metrics["quiz_rate"]["wow"] = _format_pct_change(operation_quiz_summary.get("quiz_count_week_growth"))
            behavior_metrics["quiz_rate"]["yoy"] = _format_pct_change(operation_quiz_summary.get("quiz_count_week_yoy"))

    # 5. 用户增长（日粒度）
    daily_data = query_cached(
        "dws_user_daily_quiz_stats_day",
        filters={"stat_date": {"op": "between", "value": [start_date, end_date]}},
        order_by="stat_date", order_desc=False,
    )
    if daily_data["rows"]:
        col_idx = {c: i for i, c in enumerate(daily_data["columns"])}
        rows = daily_data["rows"]
        # 计算累计均值
        sum_reg, sum_act, sum_exam = 0, 0, 0
        enriched = []
        for i, row in enumerate(rows):
            reg = float(row[col_idx["daily_register_count"]] or 0)
            act = float(row[col_idx["daily_active_count"]] or 0)
            exam = float(row[col_idx.get("daily_avg_exam", 0)] or 0) if "daily_avg_exam" in col_idx else 0
            sum_reg += reg
            sum_act += act
            sum_exam += exam
            n = i + 1
            enriched.append({
                "stat_date": row[col_idx["stat_date"]],
                "daily_register_count": row[col_idx["daily_register_count"]],
                "daily_active_count": row[col_idx["daily_active_count"]],
                "week_avg_register": round(sum_reg / n),
                "week_avg_active": round(sum_act / n),
                "week_avg_exam": round(sum_exam / n, 2),
            })

        last = enriched[-1]
        active_metrics = result["sections"].get("active", {}).get("metrics", {})
        quiz_value = last["week_avg_exam"]
        quiz_wow = "N/A"
        quiz_yoy = "N/A"
        if operation_quiz_summary:
            quiz_value = operation_quiz_summary.get("week_avg_quiz_count", quiz_value)
            quiz_wow = _format_pct_change(operation_quiz_summary.get("quiz_count_week_growth"))
            quiz_yoy = _format_pct_change(operation_quiz_summary.get("quiz_count_week_yoy"))
        result["sections"]["user_growth"] = {
            "metrics": {
                "daily_register": {"label": "本周日均注册", "value": last["week_avg_register"], "wow": active_metrics.get("reg_users", {}).get("wow", "N/A"), "yoy": active_metrics.get("reg_users", {}).get("yoy", "N/A")},
                "daily_active": {"label": "本周日均活跃", "value": last["week_avg_active"], "wow": active_metrics.get("active_users", {}).get("wow", "N/A"), "yoy": active_metrics.get("active_users", {}).get("yoy", "N/A")},
                "daily_avg_exam": {"label": "本周人均刷题", "value": quiz_value, "wow": quiz_wow, "yoy": quiz_yoy},
            },
            "trend": [{"start": e["stat_date"], "daily_register": e["daily_register_count"], "daily_active": e["daily_active_count"]} for e in enriched],
        }
    else:
        result["sections"]["user_growth"] = {"metrics": {}, "trend": []}

    return result


def _get_month_weeks(month_str: str) -> list[list[str]]:
    """从缓存中获取某月的所有周 [start_dt, end_dt]"""
    month_start = datetime.strptime(f"{month_str}-01", "%Y-%m-%d")
    if month_start.month == 12:
        next_month_start = datetime(month_start.year + 1, 1, 1)
    else:
        next_month_start = datetime(month_start.year, month_start.month + 1, 1)
    month_end = next_month_start - timedelta(days=1)
    return _get_intersected_weeks(month_start.strftime("%Y-%m-%d"), month_end.strftime("%Y-%m-%d"))


def _parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")


def _validate_range(start_str: str, end_str: str) -> tuple[datetime, datetime]:
    start_dt = _parse_date(start_str)
    end_dt = _parse_date(end_str)
    if start_dt > end_dt:
        raise ValueError("开始日期不能晚于结束日期")
    if (end_dt - start_dt).days > 179:
        raise ValueError("自定义区间跨度不能超过180天")
    return start_dt, end_dt


def _get_intersected_weeks(start_str: str, end_str: str) -> list[list[str]]:
    data = query_cached("dws_active_user_report_week", order_by="start_dt", order_desc=False)
    if not data["columns"] or not data["rows"]:
        return []

    start_dt, end_dt = _parse_date(start_str), _parse_date(end_str)
    col_idx = {c: i for i, c in enumerate(data["columns"])}
    si, ei = col_idx["start_dt"], col_idx["end_dt"]
    seen = set()
    weeks = []
    for row in data["rows"]:
        week_start = row[si]
        week_end = row[ei]
        if week_start in seen:
            continue
        week_start_dt = _parse_date(week_start)
        week_end_dt = _parse_date(week_end)
        if week_end_dt < start_dt or week_start_dt > end_dt:
            continue
        seen.add(week_start)
        weeks.append([week_start, week_end])
    weeks.sort()
    return weeks


def _aggregate_reports(period: dict, weekly_reports: list[dict], prev_reports: list[dict] | None = None) -> dict:
    if not weekly_reports:
        return {"period": period, "sections": {}, "weekly_reports": []}

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

    if prev_reports:
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

    return {"period": period, "sections": sections, "weekly_reports": weekly_reports}


def get_monthly_report(month_str: str) -> dict:
    year, month = map(int, month_str.split("-"))

    weeks = _get_month_weeks(month_str)
    if not weeks:
        return {"period": {"month": month_str}, "sections": {}, "weekly_reports": []}

    weekly_reports = [get_weekly_report(w[1]) for w in weeks]

    prev_month_dt = datetime(year, month, 1) - timedelta(days=1)
    prev_month_str = prev_month_dt.strftime("%Y-%m")
    prev_weeks = _get_month_weeks(prev_month_str)
    prev_reports = [get_weekly_report(w[1]) for w in prev_weeks] if prev_weeks else []

    return _aggregate_reports({"month": month_str, "weeks": len(weekly_reports)}, weekly_reports, prev_reports)


def get_range_report(start_str: str, end_str: str) -> dict:
    start_dt, end_dt = _validate_range(start_str, end_str)

    weeks = _get_intersected_weeks(start_str, end_str)
    if not weeks:
        return {"period": {"start": start_str, "end": end_str, "weeks": 0}, "sections": {}, "weekly_reports": []}

    weekly_reports = [get_weekly_report(w[1]) for w in weeks]

    span_days = (end_dt - start_dt).days + 1
    prev_end_dt = start_dt - timedelta(days=1)
    prev_start_dt = prev_end_dt - timedelta(days=span_days - 1)
    prev_weeks = _get_intersected_weeks(prev_start_dt.strftime("%Y-%m-%d"), prev_end_dt.strftime("%Y-%m-%d"))
    prev_reports = [get_weekly_report(w[1]) for w in prev_weeks] if prev_weeks else []

    result = _aggregate_reports({"start": start_str, "end": end_str, "weeks": len(weekly_reports)}, weekly_reports, prev_reports)

    daily_data = query_cached(
        "dws_user_daily_quiz_stats_day",
        filters={"stat_date": {"op": "between", "value": [start_str, end_str]}},
        order_by="stat_date", order_desc=False,
    )
    operation_quiz_rows = _get_operation_quiz_rows(start_str, end_str)
    if daily_data["rows"]:
        col_idx = {c: i for i, c in enumerate(daily_data["columns"])}
        rows = daily_data["rows"]
        total_reg, total_act, total_exam = 0, 0, 0
        trend = []
        for row in rows:
            reg = float(row[col_idx["daily_register_count"]] or 0)
            act = float(row[col_idx["daily_active_count"]] or 0)
            exam = float(row[col_idx.get("daily_avg_exam", 0)] or 0) if "daily_avg_exam" in col_idx else 0
            total_reg += reg
            total_act += act
            total_exam += exam
            trend.append({
                "start": row[col_idx["stat_date"]],
                "daily_register": row[col_idx["daily_register_count"]],
                "daily_active": row[col_idx["daily_active_count"]],
            })

        days = len(rows)
        quiz_value = round(total_exam / days, 2)
        if operation_quiz_rows:
            quiz_total = 0.0
            quiz_days = 0
            for row in operation_quiz_rows:
                parsed = parse_pct(row.get("avg_quiz_count"))
                if parsed is None:
                    continue
                quiz_total += parsed
                quiz_days += 1
            if quiz_days:
                quiz_value = round(quiz_total / quiz_days, 2)
        active_metrics = result["sections"].get("active", {}).get("metrics", {})
        result["sections"]["user_growth"] = {
            "metrics": {
                "daily_register": {"label": "区间日均注册", "value": round(total_reg / days), "wow": active_metrics.get("reg_users", {}).get("wow", "N/A"), "yoy": active_metrics.get("reg_users", {}).get("yoy", "N/A")},
                "daily_active": {"label": "区间日均活跃", "value": round(total_act / days), "wow": active_metrics.get("active_users", {}).get("wow", "N/A"), "yoy": active_metrics.get("active_users", {}).get("yoy", "N/A")},
                "daily_avg_exam": {"label": "区间人均刷题", "value": quiz_value, "wow": "N/A", "yoy": "N/A"},
            },
            "trend": trend,
        }
    else:
        result["sections"]["user_growth"] = {"metrics": {}, "trend": []}

    return result
