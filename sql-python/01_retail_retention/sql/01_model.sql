-- Grain: one source invoice line. Identical lines are retained because no line ID exists.
-- Signed value is recorded Quantity * UnitPrice, not accounting-certified net revenue.
CREATE OR REPLACE TABLE lines AS
SELECT *, Quantity * UnitPrice AS signed_value,
       starts_with(upper(InvoiceNo),'C') AS cancellation,
       Quantity > 0 AND UnitPrice > 0 AND NOT starts_with(upper(InvoiceNo),'C') AS purchase
FROM source_retail
WHERE InvoiceDate >= TIMESTAMP '2010-12-01' AND InvoiceDate < TIMESTAMP '2011-12-01';
CREATE OR REPLACE TABLE purchases AS
SELECT * FROM lines WHERE purchase;
-- Monetary reporting includes unidentified customers; retention does not.
CREATE OR REPLACE TABLE customer_orders AS
SELECT CustomerID, InvoiceNo, min(InvoiceDate) AS order_date,
       sum(signed_value) AS order_value, sum(Quantity) AS units
FROM purchases WHERE CustomerID IS NOT NULL
GROUP BY CustomerID, InvoiceNo;
CREATE OR REPLACE TABLE rfm AS
SELECT CustomerID, date_diff('day',max(order_date)::DATE,DATE '2011-12-01') AS recency_days,
       count(*) AS frequency_orders, sum(order_value) AS monetary_gbp,
       CASE WHEN recency_days <= 30 AND frequency_orders >= 3 THEN 'Recent repeat'
            WHEN recency_days > 90 AND frequency_orders >= 3 THEN 'Lapsed repeat'
            WHEN frequency_orders = 1 THEN 'One observed order' ELSE 'Other repeat' END AS segment
FROM customer_orders GROUP BY CustomerID;
