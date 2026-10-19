# Mortgage complaint operations

Payment issues dominated workload, while application and closing issues had higher late-response rates.

[Read the full findings report](https://idannie.github.io/sql-python/03_complaint_operations/outputs/report.html)

## Executive summary

Of 21,438 mortgage complaints received in 2024, 78.8% concerned payment-process difficulties or struggling to pay. Overall, 240 complaints were labelled as receiving a late company response, a rate of 1.12%. Application/refinancing and closing complaints made up 16.7% of volume but 43.3% of late-response labels, identifying a different priority from the largest workload categories.

## Business objective

The project assessed complaint workload and response timeliness to distinguish high-volume service issues from processes with a disproportionate concentration of late responses.

## Finding 1 · Two issues drove most of the workload

Trouble during the payment process accounted for 11,743 complaints, or 54.8% of the total. Struggling to pay a mortgage added 5,142 complaints, or 24.0%. Together, these categories represented 16,885 complaints. Payment servicing and support for borrowers facing payment difficulties therefore dominate the workload in this dataset.

## Finding 2 · Response delays were concentrated elsewhere

Application/refinancing complaints had a 2.92% late-response rate, and closing complaints had a 2.87% rate, compared with 1.12% overall. Together, they accounted for 104 of the 240 late labels despite representing only 3,581 complaints. Their late-response concentration supports a targeted process review rather than prioritization by volume alone.

## Finding 3 · The busiest month was not the weakest for timeliness

February had the largest complaint count at 1,942. November had the highest observed late-response rate at 2.10%, with 36 late labels among 1,717 complaints. This difference shows why volume and timeliness need separate monitoring; it does not establish why responses were late.

## Analysis and source code

SQL queries are in `sql/`; Python analysis is in `run.py` and `analysis.ipynb`. Saved results and charts are in `outputs/`.

[Technical documentation and reproduction steps](TECHNICAL.md) · [Data definitions](DATA_DICTIONARY.md)
