"""Complaint workload, known-label timeliness and forwarding intervals."""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from support import load_source, finish


def analyze(raw):
    df = raw.loc[
        raw.received.between("2024-01-01", "2025-01-01", inclusive="left")
        & raw["product"].eq("Mortgage")
    ].copy()
    assert (
        df.complaint_id.notna().all() and df.complaint_id.is_unique
    ), "Missing or repeated complaint ID"
    df["month"] = df.received.dt.to_period("M").dt.to_timestamp()
    df["late"] = df.timely.map({"Yes": 0.0, "No": 1.0})
    df["forwarding_days"] = (
        df.sent.dt.normalize() - df.received.dt.normalize()
    ).dt.days
    for col in ["issue", "channel", "response"]:
        df[col] = df[col].fillna("Not provided")

    def grouped(col):
        result = (
            df.groupby(col)
            .agg(
                complaints=("complaint_id", "size"),
                known_timeliness=("late", "count"),
                late_count=("late", "sum"),
            )
            .reset_index()
        )
        result["late_rate"] = result.late_count / result.known_timeliness.replace(
            0, np.nan
        )
        result["workload_share"] = result.complaints / len(df)
        return result

    monthly = grouped("month").sort_values("month")
    # Calendar spine makes changes relative to the previous calendar month.
    monthly = (
        monthly.set_index("month")
        .reindex(pd.date_range("2024-01-01", "2024-12-01", freq="MS"))
        .rename_axis("month")
        .reset_index()
    )
    for col in ["complaints", "known_timeliness", "late_count", "workload_share"]:
        monthly[col] = monthly[col].fillna(0)
    monthly["growth_rate"] = (
        monthly.complaints / monthly.complaints.shift(1).replace(0, np.nan) - 1
    )
    monthly["rolling_three_month_mean"] = monthly.complaints.rolling(
        3, min_periods=3
    ).mean()
    issues = grouped("issue").sort_values(
        ["complaints", "issue"], ascending=[False, True]
    )
    issues["cumulative_share"] = issues.workload_share.cumsum()
    channels = grouped("channel").sort_values(
        ["complaints", "channel"], ascending=[False, True]
    )
    responses = grouped("response").sort_values(
        ["complaints", "response"], ascending=[False, True]
    )
    valid = df.loc[df.forwarding_days >= 0, "forwarding_days"]
    forwarding = (
        valid.value_counts()
        .sort_index()
        .rename_axis("forwarding_days")
        .rename("complaints")
        .reset_index()
    )
    forwarding["cumulative_share"] = forwarding.complaints.cumsum() / len(valid)
    quality = pd.DataFrame(
        [
            {
                "source_rows": len(raw),
                "complaints": len(df),
                "known_timeliness": int(df.late.notna().sum()),
                "late_count": int(df.late.sum()),
                "unknown_timeliness": int(df.late.isna().sum()),
                "negative_forwarding": int((df.forwarding_days < 0).sum()),
                "missing_forwarding": int(df.forwarding_days.isna().sum()),
                "median_forwarding_days": valid.median(),
                "p90_forwarding_days": valid.quantile(0.9),
            }
        ]
    )
    tables = dict(
        monthly=monthly,
        issues=issues,
        channels=channels,
        responses=responses,
        forwarding=forwarding,
        quality=quality,
    )
    checks = {
        "monthly_reconciles": int(monthly.complaints.sum()) == len(df),
        "issues_reconcile": int(issues.complaints.sum()) == len(df),
        "channels_reconcile": int(channels.complaints.sum()) == len(df),
        "late_labels_reconcile": int(issues.late_count.sum())
        == int(df.timely.eq("No").sum()),
        "rates_bounded": bool(issues.late_rate.dropna().between(0, 1).all()),
    }
    return tables, checks


if __name__ == "__main__":
    raw, _ = load_source("complaints")
    tables, checks = analyze(raw)
    finish("complaints", "python", tables, checks)
