# Data dictionary

| Field | Meaning / handling |
|---|---|
| InvoiceNo | Invoice identifier; C prefix denotes cancellation. Read as text. |
| StockCode | Item identifier; numeric and nonnumeric codes retained as text. |
| Quantity / UnitPrice | Signed item quantity and GBP unit price; multiplication gives recorded line value. |
| InvoiceDate | Source timestamp, used without a timezone conversion. |
| CustomerID | Nullable customer identifier. Null excluded only from customer-level analyses. |
| Description / Country | Original descriptive fields; no assumption of complete descriptions. |
| recency_days | Days since last eligible purchase at snapshot. |
| frequency_orders | Number of distinct eligible invoices before snapshot. |
| monetary_gbp | Sum of eligible positive purchase value before snapshot. |
| tenure_days | Days from first observed eligible purchase to snapshot. |
| next_month_purchase | 1 if at least one eligible purchase occurs in the following calendar month. |

All predictions are for existing observed customers. Rules: Recent repeat = recency ≤30 days and ≥3 orders; Lapsed repeat = recency >90 days and ≥3 orders; One observed order = frequency 1; otherwise Other repeat. Identical invoice lines are retained. No profitability or lifetime-value estimate is inferred.
