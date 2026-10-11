"""NYC pickup demand, route diagnostics and a strictly forward seven-day backtest."""

import json
import numpy as np
import pandas as pd
import duckdb
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from pathlib import Path
from common import (
    ROOT,
    OUT,
    download,
    sql,
    result,
    chart,
    save_json,
    report,
    plt,
    StrMethodFormatter,
)


def plot_results(metrics, profile, selection, test):
    """Create the four figures from the analytical results."""
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(selection.pickup_zone, selection.training_records)
    ax.invert_yaxis()
    ax.set(
        title="Forecast zones selected before the test window",
        xlabel="Qualified pickup records, January 1-24",
    )
    chart("01_zones")
    heat = profile.pivot(index="weekday", columns="hour", values="mean_records_per_day")
    fig, ax = plt.subplots(figsize=(11, 4.2))
    im = ax.imshow(heat, aspect="auto", cmap="YlGn")
    ax.set_yticks(range(7), ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    ax.set_xticks(range(0, 24, 2))
    ax.set(title="Pickup activity by weekday and hour", xlabel="NYC local hour")
    fig.colorbar(im, ax=ax, label="Mean records per matching day")
    chart("02_heatmap")
    agg = test.groupby("hour")[
        ["records", "poisson", "last_week", "weekday_hour_mean"]
    ].sum()
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.plot(agg.index, agg.records, label="Observed", lw=2)
    ax.plot(agg.index, agg.poisson, label="Poisson calendar model", alpha=0.85)
    ax.plot(agg.index, agg.last_week, label="Previous week", alpha=0.7)
    ax.set(
        title="Seven-day forecast: ten zones combined",
        ylabel="Qualified pickup records per hour",
        xlabel="January 25-31, 2024",
    )
    ax.legend(frameon=False, ncol=3, fontsize=9)
    chart("03_forecast")
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(metrics.model, metrics.wape * 100)
    ax.set(
        title="Does the model improve on simple baselines?",
        ylabel="WAPE (%) - lower is better",
    )
    for i, v in enumerate(metrics.wape):
        ax.text(i, v * 100 + 0.3, f"{v:.1%}", ha="center")
    chart("04_comparison")


def evaluate_forecasts(panel):
    """Compare calendar and weekly forecasts on the final seven days."""
    panel["weekday"] = panel.hour.dt.dayofweek
    panel["hour_of_day"] = panel.hour.dt.hour
    panel["zone_hour"] = (
        panel.PULocationID.astype(str) + "_" + panel.hour_of_day.astype(str)
    )
    train = panel[panel.hour < "2024-01-25"].copy()
    test = panel[panel.hour >= "2024-01-25"].copy()
    cols = ["PULocationID", "hour_of_day", "weekday", "zone_hour"]
    model = make_pipeline(
        ColumnTransformer([("calendar", OneHotEncoder(handle_unknown="ignore"), cols)]),
        PoissonRegressor(alpha=0.05, max_iter=1000, tol=1e-07),
    )
    model.fit(train[cols], train.records)
    test["poisson"] = model.predict(test[cols])
    prev = train[["PULocationID", "hour", "records"]].copy()
    prev["hour"] = prev.hour + pd.Timedelta(days=7)
    test = test.merge(
        prev.rename(columns={"records": "last_week"}),
        on=["PULocationID", "hour"],
        how="left",
        validate="one_to_one",
    )
    means = (
        train.groupby(["PULocationID", "weekday", "hour_of_day"])
        .records.mean()
        .rename("weekday_hour_mean")
        .reset_index()
    )
    test = test.merge(
        means, on=["PULocationID", "weekday", "hour_of_day"], validate="many_to_one"
    )
    assert not test[["poisson", "last_week", "weekday_hour_mean"]].isna().any().any()
    rows = []
    for name in ["last_week", "weekday_hour_mean", "poisson"]:
        y = test.records.to_numpy()
        pred = test[name].to_numpy()
        rows.append(
            {
                "model": name,
                "mae_records_per_zone_hour": mean_absolute_error(y, pred),
                "rmse": np.sqrt(mean_squared_error(y, pred)),
                "wape": np.abs(y - pred).sum() / y.sum(),
                "signed_bias_share": (pred - y).sum() / y.sum(),
            }
        )
    metrics = pd.DataFrame(rows)
    metrics.to_csv(OUT / "backtest_metrics.csv", index=False)
    test.to_csv(OUT / "holdout_predictions.csv", index=False)
    return (train, test, metrics)


def main() -> None:
    specs = json.loads((ROOT / "sources.json").read_text())["files"]
    paths = {s["file"]: download(s["file"], s["url"]) for s in specs}
    db_path = OUT / "warehouse.duckdb"
    db_path.unlink(missing_ok=True)
    Path(str(db_path) + ".wal").unlink(missing_ok=True)
    con = duckdb.connect(str(db_path))
    con.read_parquet(str(paths["taxi.parquet"])).create_view(
        "source_trips", replace=True
    )
    zones = pd.read_csv(paths["zones.csv"])
    assert zones.LocationID.is_unique
    con.register("zones_input", zones)
    con.execute("CREATE OR REPLACE TABLE zones AS SELECT * FROM zones_input")
    sql(con, "01_model.sql")
    panel = sql(con, "02_hourly_panel.sql").df()
    panel.to_csv(OUT / "hourly_panel.csv", index=False)
    zp = sql(con, "03_zone_performance.sql").df()
    zp.to_csv(OUT / "zone_performance.csv", index=False)
    routes = sql(con, "04_routes.sql").df()
    routes.to_csv(OUT / "routes.csv", index=False)
    profile = result(
        con,
        "weekly_profile",
        "SELECT extract(isodow FROM tpep_pickup_datetime) AS weekday,extract(hour FROM tpep_pickup_datetime) AS hour,count(*)::DOUBLE/count(DISTINCT tpep_pickup_datetime::DATE) AS mean_records_per_day FROM demand GROUP BY 1,2 ORDER BY 1,2",
    )
    train, test, metrics = evaluate_forecasts(panel)
    raw_n = con.execute("SELECT count(*) FROM trips").fetchone()[0]
    n = con.execute("SELECT count(*) FROM demand").fetchone()[0]
    op = con.execute("SELECT count(*) FROM operations").fetchone()[0]
    selection = con.execute(
        "SELECT * FROM selected_zones ORDER BY training_records DESC"
    ).df()
    selection.to_csv(OUT / "selected_zones.csv", index=False)
    raw = pd.read_parquet(
        paths["taxi.parquet"],
        columns=["tpep_pickup_datetime", "PULocationID", "fare_amount"],
    )
    valid = (
        (raw.tpep_pickup_datetime >= "2024-01-01")
        & (raw.tpep_pickup_datetime < "2024-02-01")
        & raw.PULocationID.between(1, 263)
        & (raw.fare_amount > 0)
    )
    checks = {
        "source_rows": raw_n,
        "demand_rows": n,
        "operational_rows": op,
        "excluded_from_demand": raw_n - n,
        "excluded_from_operations_after_demand": n - op,
        "outside_month_rows": int(
            (
                (raw.tpep_pickup_datetime < "2024-01-01")
                | (raw.tpep_pickup_datetime >= "2024-02-01")
            ).sum()
        ),
        "unknown_or_nonphysical_pickup_rows": int(
            (~raw.PULocationID.between(1, 263)).sum()
        ),
        "nonpositive_or_missing_fare_rows": int((~(raw.fare_amount > 0)).sum()),
        "sql_pandas_demand_reconcile": n == int(valid.sum()),
        "zone_dimension_unique": bool(zones.LocationID.is_unique),
        "complete_hourly_grid": len(panel) == 31 * 24 * 10,
        "unique_zone_hour": not bool(panel.duplicated(["PULocationID", "hour"]).any()),
        "temporal_separation": bool(train.hour.max() < test.hour.min()),
        "test_is_seven_full_days": len(test) == 7 * 24 * 10,
        "weekly_lag_uses_only_training_dates": bool(
            (test.hour - pd.Timedelta(days=7)).max() < test.hour.min()
        ),
        "zone_metric_count_reconcile": int(zp.eligible_records.sum()) == op,
        "panel_count_reconcile": int(panel.records.sum())
        == con.execute(
            "SELECT count(*) FROM demand WHERE PULocationID IN (SELECT PULocationID FROM selected_zones)"
        ).fetchone()[0],
    }
    for k in [
        "sql_pandas_demand_reconcile",
        "zone_dimension_unique",
        "complete_hourly_grid",
        "unique_zone_hour",
        "temporal_separation",
        "test_is_seven_full_days",
        "weekly_lag_uses_only_training_dates",
        "zone_metric_count_reconcile",
        "panel_count_reconcile",
    ]:
        assert checks[k], k
    save_json("quality_checks.json", checks)
    best = metrics.sort_values("wape").iloc[0]
    model_wape = float(metrics.loc[metrics.model == "poisson", "wape"].iloc[0])
    lag_wape = float(metrics.loc[metrics.model == "last_week", "wape"].iloc[0])
    summary = {
        "source_rows": raw_n,
        "qualified_pickup_records": n,
        "operational_records": op,
        "top_training_zone": selection.iloc[0].pickup_zone,
        "holdout_zone_hours": len(test),
        "best_backtest_model": best.model,
        "best_wape": float(best.wape),
        "poisson_wape": model_wape,
        "last_week_wape": lag_wape,
    }
    save_json("summary.json", summary)
    plot_results(metrics, profile, selection, test)
    report(
        "Taxi demand and operating patterns",
        "NYC yellow taxi records · January 2024 · Zone-level SQL analysis and a seven-day Python forecast",
        [
            ("Source records", f"{raw_n:,}"),
            ("Qualified pickups", f"{n:,}"),
            ("Test zone-hours", f"{len(test):,}"),
            ("Best holdout WAPE", f"{best.wape:.1%}"),
        ],
        [
            (
                "Decision to support",
                "Identify pickup patterns for dispatch planning and test whether a calendar model improves a simple weekly planning baseline. Supply, idle time and unmet demand are not available, so no profit-maximizing dispatch policy is claimed.",
            ),
            (
                "Findings",
                f"{n:,} records meet the date, positive-fare and known-pickup-zone criteria. {selection.iloc[0].pickup_zone} leads the ten zones selected from January 1-24 training data. On January 25-31, the best of the three reported methods is {best.model} with {best.wape:.1%} WAPE. The Poisson model records {model_wape:.1%}, compared with {lag_wape:.1%} for the previous-week baseline. All errors are calculated at zone-hour level before aggregation.",
            ),
            (
                "Method",
                "DuckDB joins taxi zones, creates a separate operational subset, ranks routes and builds a complete 744-hour grid for each selected zone. The Poisson regression uses zone, hour, weekday and zone-hour categories. The entire final seven days are held out. Zone selection and baseline means use training data only. No test observations enter prediction features.",
            ),
            (
                "Recommended use",
                "Start with the best simple baseline indicated by the comparison and validate it on additional months before adoption. Use the hourly profile for staffing discussions, then add vehicle availability, travel time, weather and events. Track zone-level forecast error and service outcomes before claiming an operational improvement.",
            ),
            (
                "Limits and data decisions",
                "The file contains reported records, not verified unique trips; no trip ID exists, so identical rows are not silently removed. Demand counts exclude nonpositive fares and unknown pickup zones, but do not impose distance/duration filters. A stricter 1-180 minute, 0-100 mile positive-total subset is used for operational comparisons. These analyst-chosen thresholds are documented and audited. Tips recorded for credit-card payments do not capture cash tips. Total amount includes charges and is not driver profit. This is one winter month and one holdout; the lowest test error is a descriptive comparison, not a guarantee. Local timestamp fields are treated as NYC wall time.",
            ),
        ],
        [
            (
                "01_zones.png",
                "The top ten zones are selected using the training period only.",
            ),
            (
                "02_heatmap.png",
                "Full-month descriptive profile; each weekday is normalized by its observed calendar-day count.",
            ),
            (
                "03_forecast.png",
                "Summed curves aid interpretation; metrics remain at individual zone-hour level.",
            ),
            (
                "04_comparison.png",
                "WAPE = sum of absolute errors / sum of observed records. No hyperparameter search uses the holdout.",
            ),
        ],
        [
            ("Backtest metrics", metrics),
            (
                "High-volume routes",
                routes[
                    [
                        "pickup_zone",
                        "dropoff_zone",
                        "records",
                        "median_minutes",
                        "p90_minutes",
                    ]
                ].head(8),
            ),
        ],
    )
    con.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
