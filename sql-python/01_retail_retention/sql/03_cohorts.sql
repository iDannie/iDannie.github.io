-- First OBSERVED purchase, not necessarily acquisition. Zero-fill mature cells only.
WITH firsts AS (
 SELECT CustomerID,min(date_trunc('month',order_date))::DATE AS cohort
 FROM customer_orders GROUP BY 1
), sizes AS (SELECT cohort,count(*) AS cohort_size FROM firsts GROUP BY 1),
activity AS (
 SELECT f.cohort,date_diff('month',f.cohort,date_trunc('month',o.order_date)) AS age_month,
 count(DISTINCT o.CustomerID) AS active_customers
 FROM customer_orders o JOIN firsts f USING(CustomerID) GROUP BY 1,2
), grid AS (
 SELECT s.*,r.age_month FROM sizes s CROSS JOIN range(0,12) r(age_month)
 WHERE s.cohort + r.age_month * INTERVAL '1 month' < DATE '2011-12-01'
)
SELECT g.cohort,g.age_month,g.cohort_size,coalesce(a.active_customers,0) AS active_customers,
 coalesce(a.active_customers,0)::DOUBLE/g.cohort_size AS retention
FROM grid g LEFT JOIN activity a USING(cohort,age_month) ORDER BY 1,2;
