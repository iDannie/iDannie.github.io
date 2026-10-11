-- Counts identify workload. Timeliness uses only known Yes/No labels.
WITH issues AS (
 SELECT d.issue,count(*) AS complaints,count(c.late_response) AS known_timeliness,
 sum(c.late_response) AS late_count,
 avg(c.late_response) AS late_rate,
 median(CASE WHEN forwarding_days>=0 THEN forwarding_days END) AS median_forwarding_days
 FROM complaint_fact c JOIN issue_dimension d USING(issue_key) GROUP BY d.issue
)
SELECT *,complaints::DOUBLE/sum(complaints) OVER() AS workload_share,
 sum(complaints) OVER(ORDER BY complaints DESC,issue ROWS UNBOUNDED PRECEDING)::DOUBLE/
 sum(complaints) OVER() AS cumulative_workload_share
FROM issues ORDER BY complaints DESC,issue;
