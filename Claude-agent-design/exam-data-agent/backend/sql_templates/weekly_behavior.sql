SELECT
    start_dt,
    end_dt,
    quiz_part_rate,
    LAG(quiz_part_rate, 1) OVER (ORDER BY end_dt ASC) AS last_week_quiz_part_rate,
    quiz_part_rate_yoy,
    mock_part_rate,
    LAG(mock_part_rate, 1) OVER (ORDER BY end_dt ASC) AS last_week_mock_part_rate,
    mock_part_rate_yoy,
    course_part_rate,
    LAG(course_part_rate, 1) OVER (ORDER BY end_dt ASC) AS last_week_course_part_rate,
    course_part_rate_yoy,
    avg_play_progress,
    LAG(avg_play_progress, 1) OVER (ORDER BY end_dt ASC) AS last_week_avg_play_progress,
    avg_play_progress_yoy,
    quiz_rate,
    LAG(quiz_rate, 1) OVER (ORDER BY end_dt ASC) AS last_week_quiz_rate,
    quiz_rate_yoy
FROM (
    SELECT *
    FROM dws.dws_user_behavior_report_week
    WHERE end_dt <= :end_date
    ORDER BY end_dt DESC
    LIMIT 9
) sub
ORDER BY end_dt ASC;
