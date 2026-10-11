"""Mortgage complaint workload and response monitoring; no narrative profiling."""

import json
import textwrap
import numpy as np
import pandas as pd
import duckdb
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


def wilson(k, n, z=1.96):
    k = np.asarray(k, dtype=float)
    n = np.asarray(n, dtype=float)
    p = np.divide(k, n, out=np.full_like(k, np.nan), where=n > 0)
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (np.clip(center - half, 0, 1), np.clip(center + half, 0, 1))


def plot_results(forwarding, issue, monthly, rate):
    """Create the four figures from the analytical results."""
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.plot(monthly.month, monthly.complaints, marker="o")
    ax.set(
        title="Published mortgage complaints received in 2024",
        xlabel="Receipt month (UTC)",
        ylabel="Complaints",
    )
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    chart("01_monthly")
    fig, ax = plt.subplots(figsize=(10, 5.7))
    labels = ["\n".join(textwrap.wrap(s, 43)) for s in issue.issue]
    ax.barh(labels, issue.complaints)
    ax.invert_yaxis()
    ax.set(title="Issue categories for an operational review", xlabel="Complaint count")
    chart("02_issues")
    shown = issue[issue.known_timeliness >= 100].copy()
    shown_labels = ["\n".join(textwrap.wrap(s, 43)) for s in shown.issue]
    fig, ax = plt.subplots(figsize=(10, 5.7))
    x = shown.late_rate.to_numpy() * 100
    ax.errorbar(
        x,
        np.arange(len(shown)),
        xerr=np.maximum(
            0, np.array([x - shown.wilson_low * 100, shown.wilson_high * 100 - x])
        ),
        fmt="o",
        capsize=4,
    )
    ax.set_yticks(np.arange(len(shown)), shown_labels)
    ax.axvline(rate * 100, color="#c47745", ls="--", label="Overall rate")
    ax.invert_yaxis()
    ax.set(
        title="Recorded late-response rates by issue",
        xlabel="Late responses / known timeliness (%)",
    )
    ax.legend(frameon=False)
    chart("03_timeliness")
    fig, ax = plt.subplots(figsize=(10, 4.8))
    f = forwarding.copy()
    f["cumulative"] = f.complaints.cumsum() / f.complaints.sum()
    ax.step(f.forwarding_days, f.cumulative * 100, where="post")
    ax.set_xlim(0, max(7, float(np.interp(0.99, f.cumulative, f.forwarding_days))))
    ax.set(
        title="How quickly were complaints forwarded to companies?",
        xlabel="Calendar days from receipt to sending",
        ylabel="Cumulative share of valid intervals (%)",
    )
    chart("04_forwarding")


def load_complaints():
    """Load the fixed complaint snapshot and normalize dates."""
    spec = json.loads((ROOT / "sources.json").read_text())["files"][0]
    p = download(spec["file"], spec["url"])
    raw = pd.read_csv(p, dtype={"Complaint ID": "string", "ZIP code": "string"})
    mapping = {
        "Complaint ID": "complaint_id",
        "Date received": "received",
        "Date sent to company": "sent",
        "Product": "product",
        "Sub-product": "subproduct",
        "Issue": "issue",
        "Sub-issue": "subissue",
        "Company": "company",
        "Submitted via": "channel",
        "Company response to consumer": "response",
        "Timely response?": "timely",
    }
    df = raw[list(mapping)].rename(columns=mapping)
    for col in ["received", "sent"]:
        df[col] = pd.to_datetime(df[col], utc=True, errors="coerce").dt.tz_localize(
            None
        )
    return (raw, df)


def main() -> None:
    raw, df = load_complaints()
    db_path = OUT / "warehouse.duckdb"
    db_path.unlink(missing_ok=True)
    Path(str(db_path) + ".wal").unlink(missing_ok=True)
    con = duckdb.connect(str(db_path))
    con.register("source_complaints", df)
    sql(con, "01_model.sql")
    issue = sql(con, "02_issue_priority.sql").df()
    monthly = sql(con, "03_monthly.sql").df()
    channels = sql(con, "04_channel_mix.sql").df()
    issue["wilson_low"], issue["wilson_high"] = wilson(
        issue.late_count, issue.known_timeliness
    )
    monthly["wilson_low"], monthly["wilson_high"] = wilson(
        monthly.late_count, monthly.known_timeliness
    )
    for name, d in [
        ("issue_priority", issue),
        ("monthly", monthly),
        ("channel_mix", channels),
    ]:
        d.to_csv(OUT / f"{name}.csv", index=False)
    response = result(
        con,
        "response_categories",
        "SELECT coalesce(response,'Not provided') response,count(*) complaints FROM complaint_fact GROUP BY 1 ORDER BY 2 DESC",
    )
    forwarding = result(
        con,
        "forwarding_distribution",
        "SELECT forwarding_days,count(*) complaints FROM complaint_fact WHERE forwarding_days>=0 GROUP BY 1 ORDER BY 1",
    )
    total, known, late, sameday, valid = con.execute(
        "SELECT count(*),count(late_response),sum(late_response),count(*) FILTER(WHERE forwarding_days=0),count(*) FILTER(WHERE forwarding_days>=0) FROM complaint_fact"
    ).fetchone()
    within = df[
        (df.received >= "2024-01-01")
        & (df.received < "2025-01-01")
        & (df["product"] == "Mortgage")
    ]
    checks = {
        "download_rows": len(raw),
        "analysis_rows": total,
        "excluded_outside_2024_or_product": len(raw) - total,
        "invalid_received_dates": int(df.received.isna().sum()),
        "missing_complaint_ids": int(within.complaint_id.isna().sum()),
        "duplicate_complaint_ids": int(within.complaint_id.duplicated().sum()),
        "negative_forwarding_intervals": con.execute(
            "SELECT count(*) FROM complaint_fact WHERE forwarding_days<0"
        ).fetchone()[0],
        "unknown_timeliness": total - known,
        "sql_pandas_count_reconcile": total == len(within),
        "monthly_total_reconcile": int(monthly.complaints.sum()) == total,
        "dimension_join_preserves_rows": con.execute(
            "SELECT count(*) FROM complaints"
        ).fetchone()[0]
        == total,
        "issue_total_reconcile": int(issue.complaints.sum()) == total,
        "late_label_count_reconcile": int((within.timely == "No").sum()) == late,
        "wilson_intervals_bounded": bool(
            ((issue.wilson_low >= 0) & (issue.wilson_high <= 1)).all()
        ),
    }
    assert (
        checks["missing_complaint_ids"] == 0 and checks["duplicate_complaint_ids"] == 0
    )
    for key in [
        "sql_pandas_count_reconcile",
        "monthly_total_reconcile",
        "dimension_join_preserves_rows",
        "issue_total_reconcile",
        "late_label_count_reconcile",
        "wilson_intervals_bounded",
    ]:
        assert checks[key], key
    save_json("quality_checks.json", checks)
    peak = monthly.loc[monthly.complaints.idxmax()]
    top2 = issue.head(2).workload_share.sum()
    rate = late / known
    summary = {
        "complaints": total,
        "known_timeliness": known,
        "late_count": int(late),
        "late_rate": rate,
        "same_day_forwarding_share": sameday / valid,
        "top_two_issue_workload_share": top2,
        "largest_issue": issue.iloc[0].issue,
        "largest_issue_count": int(issue.iloc[0].complaints),
        "peak_month": str(peak.month)[:7],
        "peak_month_count": int(peak.complaints),
    }
    save_json("summary.json", summary)
    plot_results(forwarding, issue, monthly, rate)
    report(
        "Mortgage complaint operations",
        "CFPB public complaints · 2024 receipt cohort · SQL workload analysis and Python rate uncertainty",
        [
            ("Complaints", f"{total:,}"),
            ("Late response labels", f"{rate:.2%}"),
            ("Top two issue share", f"{top2:.1%}"),
            ("Same-day forwarding", f"{sameday / valid:.1%}"),
        ],
        [
            (
                "Decision to support",
                "Prioritize complaint-process reviews using workload concentration and recorded response timeliness. Keep forwarding delays separate from company resolution time.",
            ),
            (
                "Findings",
                f'{total:,} mortgage complaints remain after the local 2024 receipt-date filter. The two largest issues account for {top2:.1%} of workload. The largest issue is "{issue.iloc[0].issue}" ({int(issue.iloc[0].complaints):,} records). There are {late:,} late-response labels among {known:,} known labels ({rate:.2%}). {str(peak.month)[:7]} has the largest monthly count at {int(peak.complaints):,}.',
            ),
            (
                "Method",
                "The pipeline validates complaint IDs, enforces the local date boundary and joins an issue dimension without multiplying rows. SQL computes monthly workload, issue shares, channel mix and calendar-day forwarding intervals. Python adds Wilson intervals to show how small denominators affect observed rates.",
            ),
            (
                "Recommended review",
                "Review the highest-volume issue workflows first, then inspect issues whose recorded late-response rate is high enough to warrant a case review. Compare channels and sub-products before attributing differences to process quality. Monitor monthly counts and rates separately, with explicit owners for any follow-up.",
            ),
            (
                "Interpretation limits",
                "These are complaints published by the CFPB, not a representative sample of mortgage customers or verified findings of wrongdoing. Volumes are not market-share-adjusted risk. Timely response does not mean successful resolution. Receipt-to-sending time measures forwarding, not company response duration. Wilson intervals describe binomial uncertainty under an independence model; they do not correct selection bias, company clustering or multiple comparisons. Records were retrieved in October 2026 and reflect the then-current historical snapshot. The API returned January 2025 rows, which the SQL excludes.",
            ),
        ],
        [
            (
                "01_monthly.png",
                "Complete 2024 receipt months in the downloaded public snapshot.",
            ),
            (
                "02_issues.png",
                "Workload concentration supports triage; it does not establish incidence among all mortgage customers.",
            ),
            (
                "03_timeliness.png",
                "95% Wilson intervals for issues with at least 100 known labels. Denominators and late counts are available in issue_priority.csv.",
            ),
            (
                "04_forwarding.png",
                "Calendar-day forwarding lag; invalid negative intervals are excluded and counted in the quality audit. Display focuses through approximately the 99th percentile.",
            ),
        ],
        [
            ("Response categories", response),
            (
                "Issue denominators",
                issue[["issue", "complaints", "known_timeliness", "late_count"]],
            ),
        ],
    )
    con.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
