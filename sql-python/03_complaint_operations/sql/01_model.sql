-- Grain: one public complaint ID. Company and geography are not exposure denominators.
CREATE OR REPLACE TABLE complaints AS
SELECT *, date_trunc('month',received)::DATE AS month,
 CASE WHEN timely='Yes' THEN 0 WHEN timely='No' THEN 1 ELSE NULL END AS late_response,
 date_diff('day',received::DATE,sent::DATE) AS forwarding_days
FROM source_complaints
WHERE received >= TIMESTAMP '2024-01-01' AND received < TIMESTAMP '2025-01-01'
 AND product='Mortgage';
-- Preserve missingness in source; label only presentation dimensions.
CREATE OR REPLACE TABLE issue_dimension AS
SELECT row_number() OVER(ORDER BY issue) AS issue_key,issue
FROM (SELECT DISTINCT coalesce(issue,'Not provided') AS issue FROM complaints);
CREATE OR REPLACE TABLE complaint_fact AS
SELECT c.*,d.issue_key FROM complaints c JOIN issue_dimension d
ON coalesce(c.issue,'Not provided')=d.issue;
