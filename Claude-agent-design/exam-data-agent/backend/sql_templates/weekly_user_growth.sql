SELECT
    stat_date,
    daily_register_count,
    daily_active_count,
    daily_avg_exam,
    ROUND(
        SUM(daily_register_count) OVER (ORDER BY stat_date)
        / ROW_NUMBER() OVER (ORDER BY stat_date),
    0) AS week_avg_register,
    ROUND(
        SUM(daily_active_count) OVER (ORDER BY stat_date)
        / ROW_NUMBER() OVER (ORDER BY stat_date),
    0) AS week_avg_active,
    ROUND(
        AVG(daily_avg_exam) OVER (ORDER BY stat_date),
    2) AS week_avg_exam
FROM dws.dws_user_daily_quiz_stats_day
WHERE stat_date BETWEEN :start_date AND :end_date
ORDER BY stat_date;
