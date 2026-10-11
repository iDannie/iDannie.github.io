"""Retail sales, customer segments and observed cohort retention using pandas."""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from support import load_source, finish


def analyze(raw):
    lines = raw.loc[
        raw.InvoiceDate.between("2010-12-01", "2011-12-01", inclusive="left")
    ].copy()
    lines["value"] = lines.Quantity * lines.UnitPrice
    lines["month"] = lines.InvoiceDate.dt.to_period("M").dt.to_timestamp()
    purchases = lines.loc[
        (lines.Quantity > 0)
        & (lines.UnitPrice > 0)
        & ~lines.InvoiceNo.str.upper().str.startswith("C")
    ].copy()
    monthly = (
        purchases.groupby("month")
        .agg(purchase_value=("value", "sum"), orders=("InvoiceNo", "nunique"))
        .reset_index()
    )
    signed = lines.loc[lines.UnitPrice > 0].groupby("month").value.sum()
    monthly["signed_value"] = monthly.month.map(signed)
    monthly["average_order_value"] = monthly.purchase_value / monthly.orders
    monthly["growth_rate"] = monthly.purchase_value.pct_change()
    known = purchases.dropna(subset=["CustomerID"])
    orders = (
        known.groupby(["CustomerID", "InvoiceNo"])
        .agg(date=("InvoiceDate", "min"), value=("value", "sum"))
        .reset_index()
    )
    customers = orders.groupby("CustomerID").agg(
        last=("date", "max"), frequency=("InvoiceNo", "size"), monetary=("value", "sum")
    )
    customers["recency"] = (
        pd.Timestamp("2011-12-01") - customers["last"].dt.normalize()
    ).dt.days
    customers["segment"] = np.select(
        [
            (customers.recency <= 30) & (customers.frequency >= 3),
            (customers.recency > 90) & (customers.frequency >= 3),
            customers.frequency == 1,
        ],
        ["Recent repeat", "Lapsed repeat", "One observed order"],
        default="Other repeat",
    )
    segments = (
        customers.groupby("segment")
        .agg(customers=("monetary", "size"), purchase_value=("monetary", "sum"))
        .reset_index()
        .sort_values("purchase_value", ascending=False)
    )
    activity = orders.assign(month=orders.date.dt.to_period("M").dt.to_timestamp())[
        ["CustomerID", "month"]
    ].drop_duplicates()
    first = activity.groupby("CustomerID").month.min().rename("cohort")
    activity = activity.join(first, on="CustomerID")
    activity["age_month"] = (
        (activity.month.dt.year - activity.cohort.dt.year) * 12
        + activity.month.dt.month
        - activity.cohort.dt.month
    )
    counts = activity.groupby(["cohort", "age_month"]).size()
    rows = []
    for cohort, size in first.value_counts().sort_index().items():
        for age in range(12):
            if cohort + pd.DateOffset(months=age) >= pd.Timestamp("2011-12-01"):
                break
            active = int(counts.get((cohort, age), 0))
            rows.append([cohort, age, size, active, active / size])
    cohorts = pd.DataFrame(
        rows,
        columns=["cohort", "age_month", "cohort_size", "active_customers", "retention"],
    )
    products = (
        purchases.groupby("StockCode")
        .agg(
            purchase_value=("value", "sum"),
            units=("Quantity", "sum"),
            orders=("InvoiceNo", "nunique"),
        )
        .reset_index()
    )
    products["purchase_value"] = products.purchase_value.round(2)
    products = products.sort_values(
        ["purchase_value", "StockCode"], ascending=[False, True]
    )
    products["value_share"] = products.purchase_value / products.purchase_value.sum()
    products["cumulative_share"] = products.value_share.cumsum()
    countries = (
        purchases.groupby("Country")
        .agg(purchase_value=("value", "sum"), orders=("InvoiceNo", "nunique"))
        .reset_index()
        .rename(columns={"Country": "country"})
        .sort_values(["purchase_value", "country"], ascending=[False, True])
    )
    quality = pd.DataFrame(
        [
            {
                "source_rows": len(raw),
                "window_rows": len(lines),
                "purchase_rows": len(purchases),
                "customers": len(customers),
                "duplicate_source_lines_retained": int(raw.duplicated().sum()),
                "unidentified_value_share": purchases.loc[
                    purchases.CustomerID.isna(), "value"
                ].sum()
                / purchases.value.sum(),
            }
        ]
    )
    tables = dict(
        monthly=monthly,
        cohorts=cohorts,
        segments=segments,
        products=products,
        countries=countries,
        quality=quality,
    )
    checks = {
        "sales_reconcile": bool(
            np.isclose(monthly.purchase_value.sum(), purchases.value.sum())
        ),
        "customer_segments_reconcile": int(segments.customers.sum()) == len(customers),
        "cohort_zero_is_one": bool(
            (cohorts.loc[cohorts.age_month == 0, "retention"] == 1).all()
        ),
        "retention_bounded": bool(cohorts.retention.between(0, 1).all()),
    }
    return tables, checks


if __name__ == "__main__":
    raw, _ = load_source("retail")
    tables, checks = analyze(raw)
    finish("retail", "python", tables, checks)
