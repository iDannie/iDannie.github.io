"""Source loading and report formatting; analytical logic lives in each project."""

from pathlib import Path
import hashlib
import html
import json
import shutil
import urllib.request
import zipfile

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["svg.fonttype"] = "none"

ROOT = Path(__file__).resolve().parent
PROJECTS = {
    "retail": "01_retail_retention",
    "taxi": "02_taxi_demand",
    "complaints": "03_complaint_operations",
}


def load_source(project):
    """Check official source hashes before reading the shared local cache."""
    folder = ROOT.parent / "sql-python" / PROJECTS[project]
    manifest = json.loads((folder / "sources.json").read_text())
    paths = {}
    for spec in manifest["files"]:
        path = folder / "data" / spec["file"]
        path.parent.mkdir(exist_ok=True)
        if not path.exists():
            temp = path.with_suffix(".part")
            with urllib.request.urlopen(
                spec["url"], timeout=120
            ) as response, temp.open("wb") as target:
                shutil.copyfileobj(response, target)
            temp.replace(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != spec["sha256"]:
            raise ValueError(
                "Source changed: review the download and manifest before rerunning."
            )
        paths[spec["file"]] = path
    if project == "retail":
        with zipfile.ZipFile(paths["retail.zip"]) as archive:
            with archive.open("Online Retail.xlsx") as source:
                data = pd.read_excel(
                    source,
                    dtype={
                        "InvoiceNo": "string",
                        "StockCode": "string",
                        "CustomerID": "string",
                    },
                )
        return data, None
    if project == "taxi":
        return pd.read_parquet(paths["taxi.parquet"]), pd.read_csv(paths["zones.csv"])
    # Read only fields needed for aggregate operations analysis; no narratives or addresses.
    fields = [
        "Complaint ID",
        "Date received",
        "Date sent to company",
        "Product",
        "Issue",
        "Submitted via",
        "Company response to consumer",
        "Timely response?",
    ]
    data = pd.read_csv(paths["complaints.csv"], usecols=fields, dtype="string")
    data.columns = ["complaint_id" if c == "Complaint ID" else c for c in data.columns]
    data = data.rename(
        columns={
            "Date received": "received",
            "Date sent to company": "sent",
            "Product": "product",
            "Issue": "issue",
            "Submitted via": "channel",
            "Company response to consumer": "response",
            "Timely response?": "timely",
        }
    )
    for col in ["received", "sent"]:
        data[col] = pd.to_datetime(data[col], errors="coerce", utc=True).dt.tz_localize(
            None
        )
    return data, None


def finish(project, language, tables, checks):
    """Write aggregate tables, three static charts and a short narrative report."""
    out = ROOT / language / project / "results"
    out.mkdir(exist_ok=True)
    if not all(bool(value) for value in checks.values()):
        raise AssertionError(checks)
    (out / "checks.json").write_text(json.dumps(checks, indent=2))
    for name, data in tables.items():
        data.to_csv(out / f"{name}.csv", index=False)
    text, recommendation, limits, figures = describe(project, tables)
    for name, x, y, title in figures:
        data = (
            tables[name]
            if name in ["daily", "hourly", "monthly"]
            else tables[name].head(10)
        ).copy()
        fig, ax = plt.subplots(figsize=(9, 5))
        if name in ["daily", "monthly", "hourly"]:
            ax.plot(data[x], data[y], marker="o", markersize=3, color="#245a51")
            ax.set(
                title=title,
                ylabel=y.replace("_", " ").capitalize(),
                xlabel=x.capitalize(),
            )
            if name != "hourly":
                fig.autofmt_xdate()
        else:
            import textwrap

            labels = data[x].astype(str).map(lambda value: textwrap.fill(value, 38))
            ax.barh(labels[::-1], data[y].to_numpy()[::-1], color="#245a51")
            ax.set(title=title, xlabel=y.replace("_", " ").capitalize())
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(out / f"{name}.svg", metadata={"Date": None, "Creator": None})
        plt.close(fig)
    title = {
        "retail": "Retail sales and retention",
        "taxi": "NYC taxi operations",
        "complaints": "Mortgage complaint operations",
    }[project]
    sources = json.loads(
        (ROOT.parent / "sql-python" / PROJECTS[project] / "sources.json").read_text()
    )
    references = "\n".join(f'- {r["label"]}: {r["url"]}' for r in sources["references"])
    summary = f"# {title} — {language.upper()}\n\n## Results\n\n{text}\n\n## Recommended next step\n\n{recommendation}\n\n## Scope and limits\n\n{limits}\n\n## Sources\n\n{references}\n"
    (out / "summary.md").write_text(summary)
    body = "".join(
        f"<section><h2>{h}</h2><p>{html.escape(p)}</p></section>"
        for h, p in [
            ("Results", text),
            ("Recommended next step", recommendation),
            ("Scope and limits", limits),
        ]
    )
    for name, x, y, caption in figures:
        body += f'<figure><img src="{name}.svg" alt="{caption}"><figcaption>{caption}</figcaption></figure>'
    for name, data in tables.items():
        body += f'<details><summary>{name.replace("_", " ").capitalize()} — results table</summary><p><a href="{name}.csv">Download CSV</a></p><div class="table">{data.head(15).to_html(index=False, float_format=lambda v:f"{v:,.3f}")}</div></details>'
    code = f"https://github.com/iDannie/iDannie.github.io/tree/main/separate-analysis/{language}/{project}"
    refs = "".join(
        f'<li><a href="{html.escape(r["url"],quote=True)}">{html.escape(r["label"])}</a></li>'
        for r in sources["references"]
    )
    (out / "report.html").write_text(
        f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} | {language.upper()}</title><link rel="stylesheet" href="../../../report.css"></head><body><main><nav><a href="../../../../index.html#{language}-projects">Portfolio</a><a href="{code}">View {language.upper()} code</a></nav><p class="label">DANIEL UMEADI · {language.upper()}</p><h1>{title}</h1>{body}<section><h2>Sources</h2><ul>{refs}</ul><p><a href="summary.md">Written summary</a> · <a href="checks.json">Validation results</a></p></section></main></body></html>"""
    )
    print(f"{language}/{project}: {len(tables)} tables, {len(checks)} checks passed")


def describe(project, t):
    if project == "retail":
        m, c, q = t["monthly"], t["cohorts"], t["quality"].iloc[0]
        mature = c[c.age_month == 1]
        retention = mature.active_customers.sum() / mature.cohort_size.sum()
        text = (
            f"Positive purchase value totals £{m.purchase_value.sum():,.0f}; signed value at positive prices is £{m.signed_value.sum():,.0f}. "
            f"{int(q.customers):,} identified customers are available for retention analysis. "
            f"Weighted month-one retention is {retention:.1%}. "
            f"Unidentified customers account for {q.unidentified_value_share:.1%} of purchase value."
        )
        rec = "Review lapsed repeat customers for a measured reactivation test. Use product and country concentration to prioritize investigation; check margins before offering discounts."
        limits = "UCI Online Retail, December 2010–November 2011. December 2011 is incomplete and excluded. Purchase value is not profit. Negative quantities and cancellation invoices are excluded from purchases; signed totals retain negative quantities at positive prices. Identical lines are retained because there is no line-level ID. Missing customer IDs remain in sales totals but not retention. Cohorts measure first observed purchase, not verified acquisition. Future cohort months are excluded; observed months without activity are zero."
        figures = [
            (
                "monthly",
                "month",
                "purchase_value",
                "Monthly positive purchase value (GBP)",
            ),
            ("segments", "segment", "customers", "Customers by explicit RFM segment"),
            (
                "countries",
                "country",
                "purchase_value",
                "Top markets by purchase value (GBP)",
            ),
        ]
    elif project == "taxi":
        q, forecast = t["quality"].iloc[0], t["forecast_metrics"].iloc[0]
        zones = t["zones"]
        top = zones.iloc[0]
        text = (
            f"{int(q.demand_records):,} paid January pickup records qualify for demand analysis; {int(q.operations_records):,} pass the additional trip-quality filters. "
            f"{top.zone} is the largest pickup zone with {int(top.records):,} records. "
            f"A previous-week daily baseline for January 25–31 has {forecast.wape:.1%} WAPE and {forecast.mae:,.0f} records/day MAE."
        )
        rec = "Use zone and hourly profiles to guide staffing review. Treat the previous-week forecast as a benchmark and test additional months before operational use. Compare routes and payment types within the stricter operations scope."
        limits = "NYC TLC yellow taxi records, January 2024, local wall-clock timestamps. Counts measure recorded served demand, not unmet demand or unique customers. Demand requires a positive fare and a mapped pickup zone 1–263. Operational comparisons also require 1–180 minutes, 0–100 miles (exclusive of zero) and positive total amount. Repeated rows are retained because there is no trip ID. Total charges are not driver profit. Electronic tip recording differs from cash. One week of evaluation does not establish year-round accuracy."
        figures = [
            ("daily", "day", "records", "Daily paid pickup records"),
            ("zones", "zone", "records", "Busiest pickup zones"),
            ("hourly", "hour", "records", "Pickup records by hour"),
        ]
    else:
        q = t["quality"].iloc[0]
        issues = t["issues"]
        peak = t["monthly"].sort_values("complaints", ascending=False).iloc[0]
        text = (
            f"{int(q.complaints):,} mortgage complaints fall within 2024. The two largest issues account for {issues.head(2).workload_share.sum():.1%} of workload. "
            f"{int(q.late_count):,} of {int(q.known_timeliness):,} known timeliness labels indicate a late response ({q.late_count/q.known_timeliness:.2%}). "
            f"The busiest month is {str(peak.month)[:7]} with {int(peak.complaints):,} complaints."
        )
        rec = "Prioritize the two largest issue workflows for review. Monitor volume alongside late-response counts and denominators. Investigate forwarding delays separately from company response performance."
        limits = "CFPB mortgage complaints received in 2024, using the historical snapshot downloaded October 10, 2026. Local date filtering excludes out-of-year records. These are public complaints, not a representative customer survey or verified wrongdoing. Volume is not exposure-adjusted risk. Timeliness is a response label, not evidence of resolution. Forwarding measures receipt-to-sending calendar days; missing and negative intervals are excluded from lag statistics. Unknown timeliness is excluded from rate denominators. Only aggregates are published."
        figures = [
            ("monthly", "month", "complaints", "Monthly complaint workload"),
            ("issues", "issue", "complaints", "Issue workload"),
            ("channels", "channel", "complaints", "Complaint intake channels"),
        ]
    return text, rec, limits, figures
