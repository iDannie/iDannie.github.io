# NYC taxi demand — reproducibility guide

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
.\.venv\Scripts\python.exe -m pip install -r sql-python/02_taxi_demand/requirements.txt
cd sql-python/02_taxi_demand
..\..\.venv\Scripts\python.exe test_logic.py
..\..\.venv\Scripts\python.exe run.py
```

macOS/Linux, from the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r sql-python/02_taxi_demand/requirements.txt
cd sql-python/02_taxi_demand
../../.venv/bin/python test_logic.py
../../.venv/bin/python run.py
```

Using the environment's Python directly avoids activation-policy problems on Windows. Do not run SQL files as unrelated standalone scripts: Python first registers their input data with DuckDB. The SQL dialect is DuckDB, not SQL Server or PostgreSQL.

## 2. Acquire and verify the exact source files

`common.download()` checks `data/` for each filename in `sources.json`. It can unpack a same-named `.gz` file or download a missing file to `.part` before renaming it. It calculates SHA-256 over the uncompressed file bytes and stops if the hash differs from the manifest. The original retrieval date recorded for these sources is **2026-10-10**.

A source checksum mismatch means the downloaded bytes differ; it does not automatically mean the provider's current data is incorrect. For exact reproduction, obtain the original matching snapshot. For an intentional updated-data analysis, use a separate branch, investigate differences and revise the source manifest and report only after review. Simply changing a hash to suppress the error does not reproduce the published findings.

**`taxi.parquet`** — 49961641 bytes

URL: https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet

SHA-256: `c4d59da7bbc8abaeeeb1727947ee93d9891a71acb42854bd80db1571b2030510`

**`zones.csv`** — 12331 bytes

URL: https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv

SHA-256: `1a99e105092230f8620f301edcca7f80d3080642ff404d28ed957d3fa222c8ed`

## 3. Pinned Python packages

```text
duckdb==1.5.6
pandas==2.2.3
numpy==2.3.5
matplotlib==3.10.8
pyarrow==26.0.0
scikit-learn==1.8.0
```

## 4. Load and define two analytical populations

1. Verify `taxi.parquet` and `zones.csv` against `sources.json`. DuckDB reads the Parquet as `source_trips`; pandas reads the zone lookup. Zone `LocationID` must be unique.
2. Recreate `outputs/warehouse.duckdb`, materialize the zone table and run `sql/01_model.sql`.
3. `trips` adds duration in minutes from drop-off minus pickup and a pickup timestamp truncated to the hour.
4. `demand` joins pickup zones and retains timestamps from **2024-01-01 inclusive to 2024-02-01 exclusive**, pickup IDs 1–263 and `fare_amount > 0`. Timestamps are treated as NYC local wall time.
5. `operations` is a separate, stricter subset: duration **1–180 minutes inclusive**, trip distance **>0 and ≤100 miles**, and total amount >0. These filters apply to route and operational comparisons, not the demand forecast.
6. Repeated records are retained: there is no source trip ID establishing that an identical row is a duplicate journey. Counts are described as records.

Expected counts: **2,964,624** source records, **2,914,490** demand records and **2,848,985** operational records. Therefore 50,134 are outside demand scope, and a further 65,505 are outside operational scope. Individual exclusion flags may overlap and should not be added to infer the total exclusion count.

## 5. Execute the SQL analysis in order

| SQL file | Transformation | Saved result |
|---|---|---|
| `01_model.sql` | Builds trips, demand and operations | DuckDB tables |
| `02_hourly_panel.sql` | Selects training-period top ten zones and builds zero-filled hourly series | `hourly_panel.csv`; Python also exports `selected_zones.csv` |
| `03_zone_performance.sql` | Zone-level operational counts, duration, distance, fare and credit-card tip ratios | `zone_performance.csv` |
| `04_routes.sql` | Pickup/drop-off routes with at least 100 operational records; top 30 by volume | `routes.csv` |

Zone selection uses only timestamps before **January 25**. Ties in selection are ordered by pickup ID. The panel crosses each selected zone with every hour from January 1 00:00 through January 31 23:00. Absent counts become zero. There are **744 × 10 = 7,440** zone-hours.

Python also exports `weekly_profile.csv` using weekday and hour groups from all qualifying January demand. Counts are divided by distinct observed calendar dates in each group. This is a descriptive full-month chart, not a training feature; the heatmap should not be described as an out-of-sample forecast. The group calculation counts dates represented by records rather than separately constructing a full calendar for each weekday-hour.

Routes join known drop-off zones 1–263, calculate medians and continuous 90th percentiles, and require at least 100 records. Total charges are not driver profit; recorded credit-card tips exclude cash tips.

## 6. Forecast the held-out week

`evaluate_forecasts()` creates categorical zone, hour-of-day, weekday and zone×hour features. January 1–24 supplies **5,760** training cells; January 25–31 supplies **1,680** test cells. No test labels are used to fit models or select zones.

Three methods are compared:

1. **Previous week:** shift training observations forward seven days and join on zone and hour. Every required lag comes from training dates for this seven-day test.
2. **Weekday-hour average:** calculate the training mean for each zone × weekday × hour and join it to the test grid.
3. **Poisson regression:** one-hot encode the four categorical features using `OneHotEncoder(handle_unknown="ignore")`, then fit `PoissonRegressor(alpha=0.05, max_iter=1000, tol=1e-7)`. No holdout-driven parameter search is performed.

For zone-hour actual y and prediction p: MAE = mean(|y−p|); RMSE = sqrt(mean((y−p)²)); WAPE = sum(|y−p|)/sum(y); signed bias share = sum(p−y)/sum(y). Errors are evaluated before summing zones. The aggregate forecast chart is for interpretation and does not define the evaluation grain. Predictions are saved in `holdout_predictions.csv`.

## 7. Expected results and report calculations

| Measure | Reference value | Evidence |
|---|---:|---|
| Previous-week WAPE | 14.6248% | `backtest_metrics.csv` |
| Poisson WAPE | 24.5781% | `backtest_metrics.csv` |
| Previous-week MAE | about 23.301 records / zone-hour | `backtest_metrics.csv` |
| Poisson MAE | about 39.159 records / zone-hour | `backtest_metrics.csv` |
| Leading training zone | JFK Airport, 113,476 records | `selected_zones.csv` |
| Next two training zones | Midtown Center 106,922; Upper East Side South 106,007 | `selected_zones.csv` |
| Leading operational route | Upper East Side South → Upper East Side North, 21,615 records | `routes.csv` |
| Leading route median / p90 | 6.8 / 11.95 minutes | `routes.csv` |

The report's 40.5% relative error reduction is **(Poisson WAPE − previous-week WAPE) / Poisson WAPE**. It is not a 40.5 percentage-point reduction. The displayed comparison table reads all three method results, including weekday-hour average, from the saved metrics. The lowest test error is a descriptive result for this period, not proof that the method wins in other months.

## 8. Figures and validation

`01_zones.png` plots training-zone counts; `02_heatmap.png` shows the descriptive weekday-hour profile; `03_forecast.png` sums test-period forecasts and actuals across zones; `04_comparison.png` compares model errors. The findings report displays 01, 02 and 04. Charts are generated with Matplotlib Agg at 170 dpi.

The boundary fixture checks that zero-duration paid pickups can enter demand but not operations, unknown zones and negative fares are excluded, the February boundary is excluded, and the hourly grid retains true zeros. Production checks independently reconcile demand against pandas, require a unique zone lookup and zone-hour key, enforce the 7,440-cell grid and 1,680-cell test, prove the weekly lag uses training dates, and reconcile operational and panel totals. The forecast routine also rejects missing predictions after joins.

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

Open `http://localhost:8000/sql-python/02_taxi_demand/outputs/report.html`. Serving from the root also makes the back-to-portfolio link work. The report uses local PNG files and does not require a dashboard server. Opening the HTML directly also works for reading.

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
