SELECT
    start_dt,
    end_dt,
    pay_users,
    LEAD(pay_users, 1) OVER (ORDER BY end_dt DESC) AS last_week_pay_users,
    pay_users_yoy,
    pay_conv_rate,
    LEAD(pay_conv_rate, 1) OVER (ORDER BY end_dt DESC) AS last_week_pay_conv_rate,
    pay_conv_rate_yoy,
    repurchase_rate,
    LEAD(repurchase_rate, 1) OVER (ORDER BY end_dt DESC) AS last_week_repurchase_rate,
    repurchase_rate_yoy,
    arpu,
    LEAD(arpu, 1) OVER (ORDER BY end_dt DESC) AS last_week_arpu,
    arpu_yoy
FROM (
    SELECT *
    FROM dws.dws_pay_user_report_week
    WHERE end_dt <= :end_date
    ORDER BY end_dt DESC
    LIMIT 9
) t
ORDER BY end_dt DESC
LIMIT 8;
