# Retail retention — reproducibility guide

This guide documents the implemented pipeline and the historical results behind the published findings report.

## 1. Get the code and prepare the environment

Clone the entire repository so the shared `sql-python/render_report.py` is present. These commands are run in a terminal, not inside a notebook cell.

```bash
git clone https://github.com/iDannie/iDannie.github.io.git
cd iDannie.github.io
git rev-parse HEAD
```

Record the returned commit SHA with your run. Use a separate checkout for reproduction: `run.py` deletes and rebuilds the project's `outputs/warehouse.duckdb` and overwrites its generated tables and figures. It does not modify source data.

Use Python 3.12. The project requirements pin direct dependencies; they are not a complete operating-system or transitive-dependency lockfile. Numerical matching is the target, not byte-identical image files across operating systems.

Windows PowerShell, from the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r sql-python/01_retail_retention/requirements.txt
cd sql-python/01_retail_retention
..\..\.venv\Scripts\python.exe test_logic.py
..\..\.venv\Scripts\python.exe run.py
```

macOS/Linux, from the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r sql-python/01_retail_retention/requirements.txt
cd sql-python/01_retail_retention
../../.venv/bin/python test_logic.py
../../.venv/bin/python run.py
```

Using the environment's Python directly avoids activation-policy problems on Windows. Do not run SQL files as unrelated standalone scripts: Python first registers their input data with DuckDB. The SQL dialect is DuckDB, not SQL Server or PostgreSQL.

## 2. Acquire and verify the exact source files

`common.download()` checks `data/` for each filename in `sources.json`. It can unpack a same-named `.gz` file or download a missing file to `.part` before renaming it. It calculates SHA-256 over the uncompressed file bytes and stops if the hash differs from the manifest. The original retrieval date recorded for these sources is **2026-10-10**.

A source checksum mismatch means the downloaded bytes differ; it does not automatically mean the provider's current data is incorrect. For exact reproduction, obtain the original matching snapshot. For an intentional updated-data analysis, use a separate branch, investigate differences and revise the source manifest and report only after review. Simply changing a hash to suppress the error does not reproduce the published findings.

**`retail.zip`** — 23715478 bytes

URL: https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip

SHA-256: `f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b`

## 3. Pinned Python packages

```text
duckdb==1.5.6
pandas==2.2.3
numpy==2.3.5
matplotlib==3.10.8
pyarrow==26.0.0
scikit-learn==1.8.0
openpyxl==3.1.5
```

## 4. Load and define the analytical population

1. `load_retail_data()` downloads and verifies `retail.zip`, then reads `Online Retail.xlsx` from the ZIP with pandas/openpyxl. Invoice number, stock code, description and country become string columns. Customer IDs are converted through nullable integers to strings so missing IDs remain missing.
2. A derived `data/retail.parquet` speeds subsequent runs. For a clean reproduction, remove this derived cache before `run.py`; the current loader verifies the ZIP but does not separately hash an existing Parquet cache. Preserve `retail.zip`.
3. `main()` recreates `outputs/warehouse.duckdb`, registers the dataframe as `source_retail`, and runs `sql/01_model.sql`.
4. `lines` retains timestamps from **2010-12-01 inclusive to 2011-12-01 exclusive**. The partial December 2011 source month is excluded.
5. `signed_value = Quantity × UnitPrice`. A positive purchase requires quantity > 0, price > 0 and an invoice number that does not start with C, case-insensitively. Cancellation and negative lines do not enter purchase propensity features.
6. Missing customer IDs remain in overall purchase-value totals but are excluded from `customer_orders`. Orders aggregate at **CustomerID × InvoiceNo**, using the earliest line date and summed line value. Identical source lines are retained because the source has no unique line identifier.

Expected source count: **541,909**; analytical-window count: **516,384**; excluded partial-month records: **25,525**; eligible positive purchase lines: **504,993**.

## 5. Execute the SQL analysis in order

| SQL file | Transformation | Saved result |
|---|---|---|
| `01_model.sql` | Builds `lines`, `purchases`, `customer_orders`, `rfm` | DuckDB tables; `segments.csv` exported by Python |
| `02_monthly.sql` | Monthly positive purchase value, negative-quantity credit value, signed positive-price value, distinct purchase invoices and lagged change | `monthly.csv` |
| `03_cohorts.sql` | First-observed purchase cohorts, distinct monthly active customers and mature month-age grid | `cohorts.csv` |
| `04_temporal_features.sql` | Strictly historical customer features and next-calendar-month labels | Used in Python modelling; not separately exported |

RFM uses **2011-12-01** as its reference date. Recency is days since the latest order; frequency counts customer orders; monetary value sums positive order value. Segment rules are evaluated in this order:

- Recent repeat: recency ≤ 30 days and frequency ≥ 3.
- Lapsed repeat: recency > 90 days and frequency ≥ 3.
- One observed order: frequency = 1.
- Other repeat: all remaining customers.

These rules are explicit thresholds, not learned clusters. Segment values use identified customers only.

For cohorts, month 0 is the customer's first **observed** purchase month. Retention at age m is distinct active customers at age m divided by original cohort size. Observable months with no purchases become zero; future months remain absent. Weighted month-one retention is **sum of active customers at age 1 / sum of cohort sizes at age 1**, not an unweighted average of cohort percentages.

## 6. Fit and evaluate the Python model

`evaluate_purchase_model()` uses four features: `recency_days`, `frequency_orders`, `monetary_gbp`, and `tenure_days`. Each snapshot uses orders strictly before its date. The label is any purchase during the calendar month beginning at that snapshot.

Training snapshots: **2011-08-01, 2011-09-01, 2011-10-01**. Holdout: **2011-11-01**, with November purchase labels. Customers can appear in several snapshots; this is an out-of-time test of existing-customer ranking, not a split into disjoint customers.

The pipeline applies `numpy.log1p`, then `StandardScaler`, then `LogisticRegression(max_iter=1500, random_state=42)` with scikit-learn's remaining defaults under the pinned version. The scaler is fitted on training data. There is no hyperparameter search against the holdout.

The top group uses `ceil(0.2 × holdout customers)`, giving **795** of **3,974**. Scores sort descending with stable sorting. The recency baseline sorts recency ascending with stable sorting. Lift equals selected-group purchase rate divided by the full holdout purchase rate. Deciles are assigned by sorted position and written to `holdout_deciles.csv`.

## 7. Expected results and report calculations

| Measure | Reference value | Evidence |
|---|---:|---|
| Positive purchase value | £10,027,891.864 | `summary.json`, `monthly.csv` |
| Identified customers | 4,297 | `summary.json`, `segments.csv` |
| Weighted month-one retention | 23.6537% | `summary.json`, `cohorts.csv` |
| Holdout purchase rate | 33.7443% | `model_metrics.json` |
| Top-fifth purchase rate | 67.2956% | `model_metrics.json` |
| Model lift | 1.994278× | `model_metrics.json` |
| Recency baseline lift | 1.427680× | `model_metrics.json` |
| Average precision / ROC AUC | 0.634420 / 0.734694 | `model_metrics.json` |
| Brier score / constant-rate Brier | 0.186304 / 0.227898 | `model_metrics.json` |

The report's recent-repeat concentration is calculated from `segments.csv`: **1,143 / 4,297 = 26.6%** of customers; **£5,663,850.971 / sum(segment values) = 67.5%** of identified-customer value. This denominator differs from all-customer purchase value because unidentified sales are excluded. The model lift is predictive ranking quality, not realized marketing uplift.

## 8. Figures and validation

`plot_results()` builds `01_sales.png` from monthly positive and signed values, `02_cohorts.png` from the cohort retention pivot, `03_segments.png` from segment value, and `04_holdout.png` from predicted and observed decile rates. The findings report displays the last three; all four remain available. The cohort color scale caps at 60%, although month 0 is 100%. Charts use the Agg backend, DejaVu Sans, 170 dpi and tight bounding boxes.

`test_logic.py` uses a controlled fixture to check cancellation handling, retained duplicates, missing IDs, zero prices, the December cutoff and zero-filled mature cohorts. Production assertions reconcile SQL purchase value with pandas to £0.01, require month-zero retention to equal one, bound all retention rates, reject future cohort cells and confirm temporal separation. A passed fixture is not a substitute for production reconciliation.

## Report rendering and the two reproduction modes

**Full analytical reproduction:** `python test_logic.py`, followed by `python run.py`, uses source data to rebuild the DuckDB database, analytical CSVs, JSON summaries and four PNG figures. The pipeline also writes `outputs/technical_report.html`, an automatically generated technical view of the run. It then calls the shared renderer to write `outputs/report.html`, the reviewed findings report linked from the portfolio.

**Saved-result reproduction:** from this project folder, run:

```bash
python ../render_report.py .
```

This second command uses only Python's standard library. It checks the checked-in CSV/JSON results against `report_reference.json`, confirms the three report images exist, and copies the reviewed `report_template.html` to `outputs/report.html`. It does **not** download data, rerun SQL, refit a model or regenerate charts. It is useful for rebuilding the presentation of the published analysis, but is not independent evidence that raw-data analysis was rerun.

The renderer compares reference dictionaries, row counts, row order, text, counts and numeric results. Integer counts must match; floating-point values use relative tolerance `1e-6` and absolute tolerance `1e-7`. Rows reordered by a different tool may need investigation even if values are unchanged. A mismatch stops publication of the reviewed narrative. The latest technical report and regenerated result files remain available to investigate. An already-existing findings report may still be present after a failure: a nonzero exit code means it must not be treated as the report for the new run.

The template contains the authored interpretation for this **fixed historical analysis**. It is not a general report-writing engine for new data. When results materially change, review every numerical claim, recommendation, table and caption, revise the template, and only then update the reference values. Never update reference values just to force a successful render.

## Inspect the results

From the repository root, start a local server with your environment's Python:

```bash
python -m http.server 8000
```

Open `http://localhost:8000/sql-python/01_retail_retention/outputs/report.html`. Serving from the root also makes the back-to-portfolio link work. The report uses local PNG files and does not require a dashboard server. Opening the HTML directly also works for reading.

`analysis.ipynb` provides a notebook entry point; `run.py` is the authoritative execution sequence. Inspect `outputs/summary.json` for headline results, `outputs/quality_checks.json` for reconciliation flags, and the named CSVs for denominators and underlying values. `DATA_DICTIONARY.md` describes the fields. No claim of successful reproduction should be based on viewing the saved HTML alone.

## Troubleshooting and recording a run

- **Missing package:** confirm the command uses the environment where this project's requirements were installed. `python -m pip --version` shows that environment's pip.
- **Download/TLS/network failure:** download the exact URLs in `sources.json` into `data/` using the manifest filenames, then rerun. Hash verification still applies.
- **Database locked:** close notebooks or other connections to `outputs/warehouse.duckdb` before rerunning.
- **Source hash failure:** preserve the file and investigate the source revision. Do not silently bypass the check.
- **Reference comparison failure:** inspect the named JSON key or CSV row in the error. Check source bytes, Python/dependency versions, date boundaries, filters and sorting before editing report content.
- **Missing chart:** a full run creates the four charts; saved-result rendering needs the checked-in image assets.
- **Different PNG hashes:** font rendering, library/platform differences and image metadata can change bytes without changing the plotted values. Compare analytical numbers first.

Record the Git commit, `python --version`, `python -m pip freeze`, operating system, run date, source hashes and terminal exit status. Keep the result tables and quality-check JSON with that run. Numeric validation was added for the published report snapshot; it is not a claim that all three source-data pipelines were freshly rerun when this documentation was prepared.

## Documentation release verification — 2026-10-19

The existing logic tests passed (retail: 1, taxi: 1, complaints: 2). Saved-result rendering and the `common.report()` handoff were tested for all three projects; the resulting findings HTML matched the published template byte for byte. A controlled changed-count check was rejected. These checks used Python 3.12 with DuckDB 1.5.6 and the available scientific packages; a fresh full source-data rerun under all pinned requirements was not performed for this documentation release.
