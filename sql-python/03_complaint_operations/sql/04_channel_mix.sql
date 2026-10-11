-- Within-dataset rates, not estimates of harm across the mortgage market.
SELECT coalesce(channel,'Not provided') AS channel,count(*) AS complaints,
 count(late_response) AS known_timeliness,sum(late_response) AS late_count,avg(late_response) AS late_rate,
 quantile_cont(forwarding_days,.9) FILTER(WHERE forwarding_days>=0) AS p90_forwarding_days
FROM complaint_fact GROUP BY 1 ORDER BY complaints DESC;
