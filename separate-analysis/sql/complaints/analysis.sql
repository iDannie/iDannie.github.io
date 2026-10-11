-- DuckDB SQL. Input: source_data, restricted to operational fields by the loader.
CREATE OR REPLACE TEMP TABLE complaints AS
SELECT complaint_id,received,sent,date_trunc('month',received) AS month,
       coalesce(issue,'Not provided') AS issue,coalesce(channel,'Not provided') AS channel,
       coalesce(response,'Not provided') AS response,
       CASE timely WHEN 'Yes' THEN 0 WHEN 'No' THEN 1 END AS late,
       date_diff('day',received::DATE,sent::DATE) AS forwarding_days
FROM source_data WHERE product='Mortgage'
  AND received>=DATE '2024-01-01' AND received<DATE '2025-01-01';

CREATE OR REPLACE TABLE monthly AS
WITH calendar AS (
    SELECT month FROM generate_series(TIMESTAMP '2024-01-01',TIMESTAMP '2024-12-01',INTERVAL '1 month') t(month)
), grouped AS (
    SELECT month,count(*) AS complaints,count(late) AS known_timeliness,coalesce(sum(late),0) AS late_count
    FROM complaints GROUP BY month
), filled AS (
    SELECT c.month,coalesce(g.complaints,0) AS complaints,
           coalesce(g.known_timeliness,0) AS known_timeliness,coalesce(g.late_count,0) AS late_count
    FROM calendar c LEFT JOIN grouped g USING(month)
)
SELECT *,late_count::DOUBLE/nullif(known_timeliness,0) AS late_rate,
       complaints::DOUBLE/sum(complaints) OVER() AS workload_share,
       complaints::DOUBLE/nullif(lag(complaints) OVER(ORDER BY month),0)-1 AS growth_rate,
       CASE WHEN count(*) OVER w=3 THEN avg(complaints) OVER w END AS rolling_three_month_mean
FROM filled WINDOW w AS(ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) ORDER BY month;

-- One aggregate supports consistent issue/channel/response denominators.
CREATE OR REPLACE TEMP TABLE dimensions AS
SELECT 'issue' AS dimension,issue AS category,late FROM complaints
UNION ALL SELECT 'channel',channel,late FROM complaints
UNION ALL SELECT 'response',response,late FROM complaints;
CREATE OR REPLACE TEMP TABLE grouped_dimensions AS
SELECT dimension,category,count(*) AS complaints,count(late) AS known_timeliness,
       coalesce(sum(late),0) AS late_count,
       coalesce(sum(late),0)::DOUBLE/nullif(count(late),0) AS late_rate,
       count(*)::DOUBLE/sum(count(*)) OVER(PARTITION BY dimension) AS workload_share
FROM dimensions GROUP BY dimension,category;

CREATE OR REPLACE TABLE issues AS
SELECT category AS issue,complaints,known_timeliness,late_count,late_rate,workload_share,
       sum(workload_share) OVER(ORDER BY complaints DESC,category ROWS UNBOUNDED PRECEDING) AS cumulative_share
FROM grouped_dimensions WHERE dimension='issue' ORDER BY complaints DESC,issue;
CREATE OR REPLACE TABLE channels AS
SELECT category AS channel,complaints,known_timeliness,late_count,late_rate,workload_share
FROM grouped_dimensions WHERE dimension='channel' ORDER BY complaints DESC,channel;
CREATE OR REPLACE TABLE responses AS
SELECT category AS response,complaints,known_timeliness,late_count,late_rate,workload_share
FROM grouped_dimensions WHERE dimension='response' ORDER BY complaints DESC,response;

CREATE OR REPLACE TABLE forwarding AS
WITH counts AS (
    SELECT forwarding_days,count(*) AS complaints FROM complaints
    WHERE forwarding_days>=0 GROUP BY forwarding_days
)
SELECT *,sum(complaints) OVER(ORDER BY forwarding_days ROWS UNBOUNDED PRECEDING)::DOUBLE
         /sum(complaints) OVER() AS cumulative_share
FROM counts ORDER BY forwarding_days;
CREATE OR REPLACE TABLE quality AS
SELECT (SELECT count(*) FROM source_data) AS source_rows,count(*) AS complaints,
       count(late) AS known_timeliness,coalesce(sum(late),0) AS late_count,
       count(*)-count(late) AS unknown_timeliness,
       count(*) FILTER(WHERE forwarding_days<0) AS negative_forwarding,
       count(*) FILTER(WHERE forwarding_days IS NULL) AS missing_forwarding,
       median(forwarding_days) FILTER(WHERE forwarding_days>=0) AS median_forwarding_days,
       quantile_cont(forwarding_days,0.9) FILTER(WHERE forwarding_days>=0) AS p90_forwarding_days
FROM complaints;
CREATE OR REPLACE TABLE validation AS
SELECT 'valid_unique_ids' AS check_name,count(*)=count(complaint_id) AND count(*)=count(DISTINCT complaint_id) AS passed FROM complaints
UNION ALL SELECT 'monthly_reconcile',(SELECT sum(complaints) FROM monthly)=(SELECT count(*) FROM complaints)
UNION ALL SELECT 'issues_reconcile',(SELECT sum(complaints) FROM issues)=(SELECT count(*) FROM complaints)
UNION ALL SELECT 'channels_reconcile',(SELECT sum(complaints) FROM channels)=(SELECT count(*) FROM complaints)
UNION ALL SELECT 'late_labels_reconcile',(SELECT sum(late_count) FROM issues)=(SELECT coalesce(sum(late),0) FROM complaints)
UNION ALL SELECT 'rates_bounded',NOT EXISTS(SELECT 1 FROM issues WHERE late_rate NOT BETWEEN 0 AND 1);
