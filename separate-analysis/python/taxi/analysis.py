"""Taxi activity, operating profiles and a simple previous-week baseline."""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from support import load_source, finish


def analyze(raw, lookup):
    assert lookup.LocationID.is_unique, "Zone lookup must have one row per ID"
    mask = (
        raw.tpep_pickup_datetime.between("2024-01-01", "2024-02-01", inclusive="left")
        & raw.PULocationID.between(1, 263)
        & (raw.fare_amount > 0)
    )
    demand = raw.loc[mask].merge(
        lookup[["LocationID", "Zone"]],
        left_on="PULocationID",
        right_on="LocationID",
        validate="many_to_one",
    )
    demand["day"] = demand.tpep_pickup_datetime.dt.normalize()
    demand["hour"] = demand.tpep_pickup_datetime.dt.hour
    demand["minutes"] = (
        demand.tpep_dropoff_datetime - demand.tpep_pickup_datetime
    ).dt.total_seconds() / 60
    operations = demand.loc[
        demand.minutes.between(1, 180)
        & demand.trip_distance.between(0, 100, inclusive="right")
        & (demand.total_amount > 0)
    ].copy()
    daily = (
        demand.groupby("day")
        .size()
        .reindex(pd.date_range("2024-01-01", "2024-01-31"), fill_value=0)
        .rename("records")
        .rename_axis("day")
        .reset_index()
    )
    daily["rolling_seven_day_mean"] = daily.records.rolling(7, min_periods=7).mean()
    hourly = (
        demand.groupby("hour")
        .size()
        .reindex(range(24), fill_value=0)
        .rename("records")
        .reset_index()
    )
    zones = (
        demand.groupby(["PULocationID", "Zone"])
        .size()
        .rename("records")
        .reset_index()
        .rename(columns={"Zone": "zone"})
        .sort_values(["records", "PULocationID"], ascending=[False, True])
    )
    zones["workload_share"] = zones.records / zones.records.sum()
    zones["cumulative_share"] = zones.workload_share.cumsum()
    routes = (
        operations.groupby(["PULocationID", "DOLocationID"])
        .agg(
            records=("minutes", "size"),
            median_minutes=("minutes", "median"),
            mean_charge=("total_amount", "mean"),
        )
        .reset_index()
    )
    routes = routes.loc[routes.records >= 100].sort_values(
        ["records", "PULocationID", "DOLocationID"], ascending=[False, True, True]
    )
    payments = (
        operations.groupby("payment_type", dropna=False)
        .agg(
            records=("minutes", "size"),
            mean_charge=("total_amount", "mean"),
            mean_recorded_tip=("tip_amount", "mean"),
        )
        .reset_index()
    )
    forecast = daily[["day", "records"]].copy()
    forecast["prediction"] = forecast.records.shift(7)
    forecast = forecast.loc[forecast.day >= "2024-01-25"].copy()
    forecast["error"] = forecast.prediction - forecast.records
    forecast_metrics = pd.DataFrame(
        [
            {
                "mae": forecast.error.abs().mean(),
                "wape": forecast.error.abs().sum() / forecast.records.sum(),
                "bias_share": forecast.error.sum() / forecast.records.sum(),
            }
        ]
    )
    quality = pd.DataFrame(
        [
            {
                "source_rows": len(raw),
                "demand_records": len(demand),
                "operations_records": len(operations),
                "excluded_demand_records": len(raw) - len(demand),
            }
        ]
    )
    tables = dict(
        daily=daily,
        hourly=hourly,
        zones=zones,
        routes=routes,
        payments=payments,
        forecast=forecast,
        forecast_metrics=forecast_metrics,
        quality=quality,
    )
    checks = {
        "daily_reconciles": int(daily.records.sum()) == len(demand),
        "zone_reconciles": int(zones.records.sum()) == len(demand),
        "hour_reconciles": int(hourly.records.sum()) == len(demand),
        "seven_holdout_days": len(forecast) == 7,
        "predictions_complete": bool(forecast.prediction.notna().all()),
        "operations_subset": len(operations) <= len(demand),
    }
    return tables, checks


if __name__ == "__main__":
    raw, zones = load_source("taxi")
    tables, checks = analyze(raw, zones)
    finish("taxi", "python", tables, checks)
