SELECT
    start_dt,
    end_dt,
    reg_users,
    LEAD(reg_users, 1) OVER (ORDER BY end_dt DESC) AS last_week_reg_users,
    reg_users_yoy,
    active_users,
    LEAD(active_users, 1) OVER (ORDER BY end_dt DESC) AS last_week_active_users,
    active_users_yoy,
    valid_active_users,
    LEAD(valid_active_users, 1) OVER (ORDER BY end_dt DESC) AS last_week_valid_active_users,
    valid_active_users_yoy
FROM (
    SELECT *
    FROM dws.dws_active_user_report_week
    WHERE end_dt <= :end_date
    ORDER BY end_dt DESC
    LIMIT 9
) t
ORDER BY end_dt DESC
LIMIT 8;
