SELECT
    start_dt,
    end_dt,
    n1_ret_rate,
    LEAD(n1_ret_rate, 1) OVER (ORDER BY end_dt DESC) AS last_week_n1_ret_rate,
    n1_ret_rate_yoy,
    w_ret_rate,
    LEAD(w_ret_rate, 1) OVER (ORDER BY end_dt DESC) AS last_week_w_ret_rate,
    w_ret_rate_yoy
FROM (
    SELECT *
    FROM dws.dws_retention_user_report_week
    WHERE end_dt <= :end_date
    ORDER BY end_dt DESC
    LIMIT 9
) t
ORDER BY end_dt DESC
LIMIT 8;
