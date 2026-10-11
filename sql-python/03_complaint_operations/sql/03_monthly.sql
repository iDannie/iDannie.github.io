WITH months AS (SELECT unnest(generate_series(DATE '2024-01-01',DATE '2024-12-01',INTERVAL '1 month'))::DATE AS month),
metrics AS (
 SELECT month,count(*) AS complaints,count(late_response) AS known_timeliness,
 sum(late_response) AS late_count,
 count(*) FILTER(WHERE forwarding_days=0) AS same_day_forwarded,
 count(*) FILTER(WHERE forwarding_days>=0) AS valid_forwarding,
 quantile_cont(forwarding_days,.9) FILTER(WHERE forwarding_days>=0) AS p90_forwarding_days
 FROM complaint_fact GROUP BY month
)
SELECT m.month,coalesce(complaints,0) AS complaints,known_timeliness,late_count,
 late_count::DOUBLE/nullif(known_timeliness,0) AS late_rate,
 same_day_forwarded::DOUBLE/nullif(valid_forwarding,0) AS same_day_forwarding_share,p90_forwarding_days,
 complaints-lag(complaints) OVER(ORDER BY m.month) AS month_over_month_change
FROM months m LEFT JOIN metrics USING(month) ORDER BY month;
