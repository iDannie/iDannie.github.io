# Separate Python and SQL analyses

Three datasets, each analyzed independently in Python and SQL. The original combined projects remain in `../sql-python/`.

| Project | Coverage | Outputs per version |
| --- | --- | --- |
| Retail | Monthly sales, order value, product and country concentration, RFM segments, mature customer cohorts, data quality | Six tables, three charts, findings and recommendations |
| NYC taxi | Daily/hourly activity, zones, routes, payment profiles, seven-day baseline evaluation, data quality | Eight tables, three charts, findings and recommendations |
| Mortgage complaints | Monthly trends, issues, intake channels, responses, forwarding intervals, known-label timeliness, data quality | Six tables, three charts, findings and recommendations |

## Run

From the repository root, using Python 3.11 or later:

```bash
python -m pip install -r separate-analysis/requirements.txt

python separate-analysis/python/retail/analysis.py
python separate-analysis/python/taxi/analysis.py
python separate-analysis/python/complaints/analysis.py

python separate-analysis/run_sql.py retail
python separate-analysis/run_sql.py taxi
python separate-analysis/run_sql.py complaints

python separate-analysis/verify_results.py
python separate-analysis/test_boundaries.py
```

Open each project's `results/report.html`. The report contains a short narrative, three static charts and expandable results tables. Full aggregate tables are available as CSV; `summary.md` contains the written findings. There are no dashboards or machine-learning dependencies.

## How the versions differ

- **Python:** direct pandas filtering, grouping, merging and small functions. No SQL engine is used in its analytical scripts. The taxi forecast is a transparent previous-week baseline.
- **SQL:** DuckDB SQL with staged tables, CTEs, calendar/cohort spines, conditional aggregation, `LAG`, rolling windows, cumulative shares, percentiles and reconciliation checks. `run_sql.py` only registers source tables, executes the SQL and exports results. All analytical calculations are in `analysis.sql`.
- `support.py` handles source download, hash verification and presentation for both versions. It does not perform the project analyses; summary sentences format the aggregate results.
- The same definitions are deliberately used in both implementations. They are six code examples across three datasets, not six unrelated business projects. `verify_results.py` compares every exported table, including dates, counts, ratios and missing values.

## Data and reproducibility

Official source URLs, attribution, retrieval dates and SHA-256 hashes are retained in the original projects' `sources.json` files. Both versions read those manifests and the same local download cache. A clean run downloads approximately 80 MB; reading the retail workbook takes longer than reading the other sources. If an official historical export changes, the hash check stops the run rather than silently producing different findings.

Raw records, customer-level outputs and database files are not published. The scripts export aggregate results only. CFPB narratives, company names, ZIP codes and addresses are not read by these analyses. UCI data attribution remains in each report. Definitions, exclusions and interpretation limits accompany each result summary.
