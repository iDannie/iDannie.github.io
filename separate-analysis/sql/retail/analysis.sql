-- DuckDB SQL. Input: source_data, one row per original invoice line.
-- Keep repeated lines: no line-level identifier establishes duplicates.
CREATE OR REPLACE TEMP TABLE lines AS
SELECT *, Quantity * UnitPrice AS value, date_trunc('month',InvoiceDate) AS month
FROM source_data
WHERE InvoiceDate >= DATE '2010-12-01' AND InvoiceDate < DATE '2011-12-01';

CREATE OR REPLACE TEMP TABLE purchases AS
SELECT * FROM lines
WHERE Quantity > 0 AND UnitPrice > 0 AND NOT starts_with(upper(InvoiceNo),'C');

CREATE OR REPLACE TABLE monthly AS
WITH sales AS (
    SELECT month, sum(value) AS purchase_value, count(DISTINCT InvoiceNo) AS orders
    FROM purchases GROUP BY month
), signed AS (
    SELECT month, sum(value) AS signed_value FROM lines WHERE UnitPrice > 0 GROUP BY month
)
SELECT s.*, n.signed_value, s.purchase_value / nullif(s.orders,0) AS average_order_value,
       s.purchase_value / nullif(lag(s.purchase_value) OVER(ORDER BY s.month),0)-1 AS growth_rate
FROM sales s JOIN signed n USING(month) ORDER BY month;

CREATE OR REPLACE TEMP TABLE orders AS
SELECT CustomerID, InvoiceNo, min(InvoiceDate) AS order_date, sum(value) AS order_value
FROM purchases WHERE CustomerID IS NOT NULL GROUP BY CustomerID, InvoiceNo;

CREATE OR REPLACE TEMP TABLE customers AS
SELECT CustomerID, count(*) AS frequency, sum(order_value) AS monetary,
       date_diff('day',max(order_date)::DATE,DATE '2011-12-01') AS recency,
       CASE WHEN recency <= 30 AND frequency >= 3 THEN 'Recent repeat'
            WHEN recency > 90 AND frequency >= 3 THEN 'Lapsed repeat'
            WHEN frequency = 1 THEN 'One observed order' ELSE 'Other repeat' END AS segment
FROM orders GROUP BY CustomerID;

CREATE OR REPLACE TABLE segments AS
SELECT segment,count(*) AS customers,sum(monetary) AS purchase_value
FROM customers GROUP BY segment ORDER BY purchase_value DESC;

-- Mature cohort grid: genuine no-activity months become zero; future months never enter.
CREATE OR REPLACE TABLE cohorts AS
WITH firsts AS (
    SELECT CustomerID,min(date_trunc('month',order_date)) AS cohort FROM orders GROUP BY CustomerID
), sizes AS (
    SELECT cohort,count(*) AS cohort_size FROM firsts GROUP BY cohort
), activity AS (
    SELECT f.cohort,date_diff('month',f.cohort,o.order_date) AS age_month,
           count(DISTINCT o.CustomerID) AS active_customers
    FROM orders o JOIN firsts f USING(CustomerID) GROUP BY 1,2
), grid AS (
    SELECT s.*,r.age_month FROM sizes s CROSS JOIN range(12) r(age_month)
    WHERE cohort + age_month * INTERVAL '1 month' < DATE '2011-12-01'
)
SELECT g.*,coalesce(a.active_customers,0) AS active_customers,
       coalesce(a.active_customers,0)::DOUBLE/g.cohort_size AS retention
FROM grid g LEFT JOIN activity a USING(cohort,age_month) ORDER BY cohort,age_month;

-- Stable secondary ordering makes cumulative concentration reproducible under ties.
CREATE OR REPLACE TABLE products AS
WITH grouped AS (
    SELECT StockCode,round(sum(value),2) AS purchase_value,sum(Quantity) AS units,
           count(DISTINCT InvoiceNo) AS orders FROM purchases GROUP BY StockCode
)
SELECT *,purchase_value/sum(purchase_value) OVER() AS value_share,
       sum(purchase_value) OVER(ORDER BY purchase_value DESC,StockCode ROWS UNBOUNDED PRECEDING)
         /sum(purchase_value) OVER() AS cumulative_share
FROM grouped ORDER BY purchase_value DESC,StockCode;

CREATE OR REPLACE TABLE countries AS
SELECT Country AS country,sum(value) AS purchase_value,count(DISTINCT InvoiceNo) AS orders
FROM purchases GROUP BY Country ORDER BY purchase_value DESC,country;

CREATE OR REPLACE TABLE quality AS
SELECT (SELECT count(*) FROM source_data) AS source_rows,
       (SELECT count(*) FROM lines) AS window_rows,count(*) AS purchase_rows,
       (SELECT count(*) FROM customers) AS customers,
       (SELECT count(*) FROM source_data)-(SELECT count(*) FROM (SELECT DISTINCT * FROM source_data)) AS duplicate_source_lines_retained,
       sum(value) FILTER(WHERE CustomerID IS NULL)/sum(value) AS unidentified_value_share
FROM purchases;

CREATE OR REPLACE TABLE validation AS
SELECT 'sales_reconcile' AS check_name,abs((SELECT sum(purchase_value) FROM monthly)-(SELECT sum(value) FROM purchases))<0.01 AS passed
UNION ALL SELECT 'segments_reconcile',(SELECT sum(customers) FROM segments)=(SELECT count(*) FROM customers)
UNION ALL SELECT 'cohort_zero_is_one',NOT EXISTS(SELECT 1 FROM cohorts WHERE age_month=0 AND retention<>1)
UNION ALL SELECT 'retention_bounded',NOT EXISTS(SELECT 1 FROM cohorts WHERE retention NOT BETWEEN 0 AND 1);
