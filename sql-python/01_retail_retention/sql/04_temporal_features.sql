-- Every predictor uses history strictly before its snapshot; label uses the next calendar month.
WITH snapshots AS (
 SELECT * FROM (VALUES (DATE '2011-08-01'),(DATE '2011-09-01'),
 (DATE '2011-10-01'),(DATE '2011-11-01')) v(snapshot)
), features AS (
 SELECT s.snapshot,o.CustomerID,
 date_diff('day',max(o.order_date)::DATE,s.snapshot) AS recency_days,
 count(*) AS frequency_orders,sum(o.order_value) AS monetary_gbp,
 date_diff('day',min(o.order_date)::DATE,s.snapshot) AS tenure_days
 FROM snapshots s JOIN customer_orders o ON o.order_date < s.snapshot
 GROUP BY 1,2
)
SELECT f.*, CASE WHEN EXISTS (
 SELECT 1 FROM customer_orders y WHERE y.CustomerID=f.CustomerID
 AND y.order_date>=f.snapshot AND y.order_date<f.snapshot+INTERVAL '1 month'
) THEN 1 ELSE 0 END AS next_month_purchase
FROM features f ORDER BY snapshot,CustomerID;
