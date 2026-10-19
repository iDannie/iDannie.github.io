# Retail retention and repeat-purchase targeting

Customer history identified a high-propensity group with twice the overall repeat-purchase rate.

[Read the full findings report](https://idannie.github.io/sql-python/01_retail_retention/outputs/report.html)

## Executive summary

The analysis covered £10.03 million in positive purchase value and 4,297 identified customers. Only 23.7% of customers returned in the month after their first observed purchase. A logistic regression model identified a top-fifth customer group with a 67.3% November purchase rate, compared with 33.7% across the holdout population. The model also outperformed a simple recency ranking, making it a stronger candidate for prioritizing a retention campaign.

## Business objective

The project evaluated customer retention and compared two ways of prioritizing existing customers for repeat-purchase outreach: a simple recency rule and a model using customer purchase history.

## Finding 1 · Repeat purchasing was concentrated

The 1,143 customers classified as recent repeat buyers represented 26.6% of identified customers and £5.66 million in positive purchase value—67.5% of identified-customer value. By contrast, 1,538 customers had only one observed order. This concentration makes retaining active repeat buyers commercially important, while first-to-second-purchase conversion remains a distinct opportunity.

## Finding 2 · The first repeat purchase was a weak point

Weighted month-one retention was 23.7% across cohorts with a complete following month. Most customers therefore did not purchase in the immediately following month. The cohort view separates this early drop-off from later purchasing patterns; a missed month does not by itself establish permanent churn.

## Finding 3 · The model improved customer prioritization

Among 3,974 customers evaluated in November, the model’s highest-ranked 795 customers had a 67.3% purchase rate. Its 1.99× lift exceeded the recency rule’s 1.43× lift. Average precision was 0.634 and ROC AUC was 0.735. These results demonstrate improved ranking of likely repeat purchasers, rather than a measured increase caused by marketing.

## Analysis and source code

SQL queries are in `sql/`; Python analysis is in `run.py` and `analysis.ipynb`. Saved results and charts are in `outputs/`.

[Technical documentation and reproduction steps](TECHNICAL.md) · [Data definitions](DATA_DICTIONARY.md)
