-- Full calendar months only. Positive sales and signed credits remain separate.
WITH monthly AS (
 SELECT date_trunc('month',InvoiceDate)::DATE AS month,
 sum(CASE WHEN purchase THEN signed_value ELSE 0 END) AS gross_positive_gbp,
 sum(CASE WHEN Quantity < 0 AND UnitPrice > 0 THEN -signed_value ELSE 0 END) AS credit_value_gbp,
 sum(CASE WHEN UnitPrice > 0 THEN signed_value ELSE 0 END) AS signed_net_gbp,
 count(DISTINCT CASE WHEN purchase THEN InvoiceNo END) AS purchase_invoices
 FROM lines GROUP BY 1
)
SELECT *, signed_net_gbp-lag(signed_net_gbp) OVER(ORDER BY month) AS net_change_gbp
FROM monthly ORDER BY month;
