# Mortgage complaint operations — reproducibility guide

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
.\.venv\Scripts\python.exe -m pip install -r sql-python/03_complaint_operations/requirements.txt
cd sql-python/03_complaint_operations
..\..\.venv\Scripts\python.exe test_logic.py
..\..\.venv\Scripts\python.exe run.py
```

macOS/Linux, from the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r sql-python/03_complaint_operations/requirements.txt
cd sql-python/03_complaint_operations
../../.venv/bin/python test_logic.py
../../.venv/bin/python run.py
```

Using the environment's Python directly avoids activation-policy problems on Windows. Do not run SQL files as unrelated standalone scripts: Python first registers their input data with DuckDB. The SQL dialect is DuckDB, not SQL Server or PostgreSQL.

## 2. Acquire and verify the exact source files

`common.download()` checks `data/` for each filename in `sources.json`. It can unpack a same-named `.gz` file or download a missing file to `.part` before renaming it. It calculates SHA-256 over the uncompressed file bytes and stops if the hash differs from the manifest. The original retrieval date recorded for these sources is **2026-10-10**.

A source checksum mismatch means the downloaded bytes differ; it does not automatically mean the provider's current data is incorrect. For exact reproduction, obtain the original matching snapshot. For an intentional updated-data analysis, use a separate branch, investigate differences and revise the source manifest and report only after review. Simply changing a hash to suppress the error does not reproduce the published findings.

**`complaints.csv`** — 6581433 bytes

URL: https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/?date_received_min=2024-01-01&date_received_max=2025-01-01&product=Mortgage&format=csv&no_aggs=true

SHA-256: `323267d23647819303def9d2da9675820be085c5168ab7bfcd07818a51c0f764`

## 3. Pinned Python packages

```text
duckdb==1.5.6
pandas==2.2.3
numpy==2.3.5
matplotlib==3.10.8
```

## 4. Obtain the historical export and define the cohort

The exact source is the CFPB Mortgage CSV export retrieved **October 10, 2026**, identified by the SHA-256 below. The repository deliberately contains analytical aggregates and code, not raw complaint records. The official API can revise historical exports. If it no longer returns the matching bytes, the published raw-data result cannot be exactly reconstructed from that newer export alone. A matching privately retained source is required; saved-result report rendering remains available from the checked-in aggregates.

1. `load_complaints()` verifies `data/complaints.csv`. Pandas reads complaint IDs and ZIP codes as strings, then selects only the mapped analytical columns. ZIP codes and consumer narratives are not used in the retained analysis dataframe.
2. Source columns map to `complaint_id`, `received`, `sent`, `product`, `subproduct`, `issue`, `subissue`, `company`, `channel`, `response` and `timely`.
3. Receipt and sending dates parse with `utc=True, errors="coerce"`, then lose timezone metadata after UTC normalization. Invalid dates become missing.
4. `sql/01_model.sql` retains product exactly `Mortgage` and **2024-01-01 ≤ received < 2025-01-01**. Local filtering is authoritative even though the API request also supplies dates. The original response included rows outside the final analytical window.
5. `late_response` is 0 for `Yes`, 1 for `No`, and NULL otherwise. Unknown values are neither timely nor late. `forwarding_days` is the difference between receipt and sending calendar dates, not elapsed hours and not company response time.
6. An issue dimension labels missing issues `Not provided` for grouping. The join must not multiply complaint rows. Missing or duplicated complaint IDs cause the production pipeline to fail rather than silently deduplicate.

Expected export rows: **21,473**; final cohort: **21,438**; excluded by local scope: **35**. In the reference cohort there are no missing or duplicated IDs and no unknown timeliness labels.

## 5. Execute the SQL analysis in order

| SQL file | Transformation | Saved result |
|---|---|---|
| `01_model.sql` | Builds complaints, issue dimension and complaint fact table | DuckDB tables |
| `02_issue_priority.sql` | Issue volume, known labels, late count/rate, forwarding median and Pareto shares | `issue_priority.csv` |
| `03_monthly.sql` | Complete 2024 calendar, monthly workload/rates, p90 forwarding and monthly changes | `monthly.csv` |
| `04_channel_mix.sql` | Counts and response rates by submission channel | `channel_mix.csv` |

Python additionally exports `response_categories.csv` and `forwarding_distribution.csv` using SQL. Missing response categories receive a display label. Forwarding distributions exclude negative or missing intervals; those exclusions must remain separate from timeliness labels.

Issue workload share = issue count / all complaints. Cumulative share follows descending volume, with issue text as a tie-breaker. Late rate = count of `No` / count of known `Yes` or `No`, **not automatically total complaints**. Same-day forwarding share = zero-day intervals / known nonnegative intervals. Monthly counts use a calendar join; empty-month rates remain undefined rather than automatically becoming 0%.

## 6. Add uncertainty and generate figures in Python

`wilson(k, n, z=1.96)` computes a Wilson interval for each issue and month, where k is late count and n is known timeliness. Let p = k/n and d = 1 + z²/n. The centre is (p + z²/(2n))/d; the half-width is z × sqrt(p(1−p)/n + z²/(4n²))/d. Bounds are clipped to [0,1]. A zero denominator is not evidence of a zero late rate.

`01_monthly.png` plots monthly complaint volume. `02_issues.png` plots issue counts. `03_timeliness.png` shows observed rates and 95% Wilson intervals only for issues with at least 100 known labels, with the overall rate as a reference. `04_forwarding.png` shows the cumulative share by forwarding days, with the displayed range focused through approximately the 99th percentile. The findings report displays 02, 03 and 01. All four remain available.

Intervals assume independent binary outcomes. They do not correct for selection bias, company clustering or multiple comparisons and do not establish causal process failures. No predictive machine-learning model is fitted in this project.

## 7. Expected results and report calculations

| Measure | Reference value | Evidence |
|---|---:|---|
| Complaint cohort | 21,438 | `summary.json` |
| Late labels / known labels | 240 / 21,438 | `summary.json` |
| Overall late-response rate | 1.119507% | `summary.json` |
| Payment-process complaints | 11,743 | `issue_priority.csv` |
| Struggling-to-pay complaints | 5,142 | `issue_priority.csv` |
| Combined top-two share | 78.762011% | `summary.json` |
| Same-day forwarding share | 84.522810% | `summary.json` |
| Largest month by volume | February: 1,942 | `monthly.csv` |
| Highest observed monthly late rate | November: 36 / 1,717 = 2.09668% | `monthly.csv` |

Application/refinancing has **2,154** complaints and **63** late labels; closing has **1,427** complaints and **41** late labels. The report's concentration comparison is **(2,154 + 1,427) / 21,438 = 16.7% of volume**, against **(63 + 41) / 240 = 43.3% of late labels**. Their individual late rates are 2.92% and 2.87%. These are descriptive associations; complaint categories are not exposure-adjusted measures of harm.

## 8. Validation and interpretation

`test_logic.py` uses a small fixture to verify the exclusive 2025 boundary, unknown timeliness labels, preserved missing-issue rows, and Wilson bounds at zero and all successes. Production assertions reject missing or duplicate IDs, reconcile SQL counts with an independent pandas filter, reconcile monthly and issue totals, verify dimension-join row counts, reconcile late labels with source `No` values and bound intervals. Negative forwarding intervals and unknown timeliness are counted in `quality_checks.json`.

Complaint volume represents published complaints, not all mortgage customers or verified wrongdoing. A timely response is not necessarily a successful resolution. The data cannot establish staffing savings, process improvement or customer outcomes caused by implementing the recommendations.

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

Open `http://localhost:8000/sql-python/03_complaint_operations/outputs/report.html`. Serving from the root also makes the back-to-portfolio link work. The report uses local PNG files and does not require a dashboard server. Opening the HTML directly also works for reading.

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
