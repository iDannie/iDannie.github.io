"""Rebuild the retail warehouse, cohort analysis and out-of-time propensity benchmark."""

import zipfile
import json
import numpy as np
import pandas as pd
import duckdb
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
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


def plot_results(cohorts, lift, metrics, monthly, seg):
    """Create the four figures from the analytical results."""
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.plot(
        monthly.month,
        monthly.gross_positive_gbp / 1000000.0,
        label="Positive purchase value",
        marker="o",
    )
    ax.plot(
        monthly.month,
        monthly.signed_net_gbp / 1000000.0,
        label="Signed value (positive prices)",
        marker="o",
    )
    ax.set(
        title="Recorded purchase value and credits",
        ylabel="GBP millions",
        xlabel="Full calendar month",
    )
    ax.legend(frameon=False)
    chart("01_sales")
    pivot = cohorts.pivot(index="cohort", columns="age_month", values="retention")
    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(pivot.to_numpy() * 100, vmin=0, vmax=60, cmap="YlGn")
    ax.set_yticks(range(len(pivot)), [str(x)[:7] for x in pivot.index])
    ax.set_xticks(range(12))
    ax.set(
        title="Repeat purchasing by first observed purchase month",
        xlabel="Months since first observed purchase",
        ylabel="Cohort",
    )
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.iloc[i, j]
            if pd.notna(v):
                ax.text(
                    j,
                    i,
                    f"{v:.0%}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white" if v > 0.4 else "#213c38",
                )
    fig.colorbar(im, ax=ax, label="Active customers (%)")
    chart("02_cohorts")
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.barh(seg.segment, seg.positive_value_gbp / 1000000.0)
    ax.invert_yaxis()
    ax.set(
        title="Which customer segments carry recorded purchase value?",
        xlabel="Positive purchase value (GBP millions)",
    )
    chart("03_segments")
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.plot(
        lift.decile,
        lift.actual_purchase_rate * 100,
        marker="o",
        label="Observed November purchases",
    )
    ax.plot(
        lift.decile,
        lift.predicted_rate * 100,
        marker="s",
        label="Predicted probability",
    )
    ax.axhline(
        metrics["purchase_prevalence"] * 100,
        color="#c47745",
        ls="--",
        label="Holdout base rate",
    )
    ax.set(
        title="Out-of-time purchase propensity: November 2011",
        xlabel="Score decile (1 = highest propensity)",
        ylabel="Customer purchase rate (%)",
        xticks=range(1, 11),
    )
    ax.legend(frameon=False)
    chart("04_holdout")


def evaluate_purchase_model(features):
    """Fit the purchase model on earlier snapshots and evaluate November."""
    cols = ["recency_days", "frequency_orders", "monetary_gbp", "tenure_days"]
    train = features[features.snapshot < pd.Timestamp("2011-11-01")]
    test = features[features.snapshot == pd.Timestamp("2011-11-01")]
    model = make_pipeline(
        StandardScaler(), LogisticRegression(max_iter=1500, random_state=42)
    )
    model.fit(np.log1p(train[cols]), train.next_month_purchase)
    score = model.predict_proba(np.log1p(test[cols]))[:, 1]
    y = test.next_month_purchase.to_numpy()
    top = max(1, int(np.ceil(len(y) * 0.2)))
    rank = np.argsort(-score, kind="stable")
    rule_rank = np.argsort(test.recency_days.to_numpy(), kind="stable")
    metrics = {
        "test_month": "2011-11",
        "train_snapshot_months": ["2011-08", "2011-09", "2011-10"],
        "test_customers": len(test),
        "purchase_prevalence": float(y.mean()),
        "average_precision": average_precision_score(y, score),
        "roc_auc": roc_auc_score(y, score),
        "brier": brier_score_loss(y, score),
        "constant_train_rate_brier": brier_score_loss(
            y, np.repeat(train.next_month_purchase.mean(), len(y))
        ),
        "top_20pct_precision": float(y[rank[:top]].mean()),
        "top_20pct_lift": float(y[rank[:top]].mean() / y.mean()),
        "recency_rule_top20_lift": float(y[rule_rank[:top]].mean() / y.mean()),
        "top_group_n": top,
    }
    save_json("model_metrics.json", metrics)
    lift = (
        pd.DataFrame({"score": score, "label": y})
        .sort_values("score", ascending=False, kind="stable")
        .reset_index(drop=True)
    )
    lift["decile"] = np.minimum(10, np.arange(len(lift)) * 10 // len(lift) + 1)
    lift = (
        lift.groupby("decile")
        .agg(
            customers=("label", "size"),
            actual_purchase_rate=("label", "mean"),
            predicted_rate=("score", "mean"),
        )
        .reset_index()
    )
    lift.to_csv(OUT / "holdout_deciles.csv", index=False)
    return (metrics, lift)


def load_retail_data():
    """Load verified invoice data and preserve identifier types."""
    archive = download(
        "retail.zip", json.loads((ROOT / "sources.json").read_text())["files"][0]["url"]
    )
    cached = ROOT / "data/retail.parquet"
    if cached.exists():
        df = pd.read_parquet(cached)
    else:
        with zipfile.ZipFile(archive) as z, z.open("Online Retail.xlsx") as f:
            df = pd.read_excel(f)
        for col in ["InvoiceNo", "StockCode", "Description", "Country"]:
            df[col] = df[col].astype("string")
        df["CustomerID"] = df.CustomerID.astype("Int64").astype("string")
        df.to_parquet(cached, index=False)
    return df


def main() -> None:
    df = load_retail_data()
    db_path = OUT / "warehouse.duckdb"
    db_path.unlink(missing_ok=True)
    Path(str(db_path) + ".wal").unlink(missing_ok=True)
    con = duckdb.connect(str(db_path))
    con.register("source_retail", df)
    sql(con, "01_model.sql")
    monthly = sql(con, "02_monthly.sql").df()
    monthly.to_csv(OUT / "monthly.csv", index=False)
    cohorts = sql(con, "03_cohorts.sql").df()
    cohorts.to_csv(OUT / "cohorts.csv", index=False)
    features = sql(con, "04_temporal_features.sql").df()
    seg = result(
        con,
        "segments",
        "SELECT segment,count(*) customers,sum(monetary_gbp) positive_value_gbp,median(recency_days) median_recency_days FROM rfm GROUP BY segment ORDER BY positive_value_gbp DESC",
    )
    k = con.execute(
        "SELECT count(*),sum(signed_value),count(DISTINCT InvoiceNo) FROM purchases"
    ).fetchone()
    n_customer = con.execute("SELECT count(*) FROM rfm").fetchone()[0]
    identified = con.execute("SELECT sum(order_value) FROM customer_orders").fetchone()[
        0
    ]
    one_month = cohorts[cohorts.age_month == 1]
    weighted_retention = one_month.active_customers.sum() / one_month.cohort_size.sum()
    metrics, lift = evaluate_purchase_model(features)
    in_window = df[(df.InvoiceDate >= "2010-12-01") & (df.InvoiceDate < "2011-12-01")]
    mask = (
        (in_window.Quantity > 0)
        & (in_window.UnitPrice > 0)
        & ~in_window.InvoiceNo.str.upper().str.startswith("C")
    )
    independent = (
        in_window.loc[mask, "Quantity"] * in_window.loc[mask, "UnitPrice"]
    ).sum()
    checks = {
        "source_rows": len(df),
        "window_rows": len(in_window),
        "excluded_partial_december_rows": len(df) - len(in_window),
        "missing_customer_rows_source": int(df.CustomerID.isna().sum()),
        "exact_duplicate_rows_retained_source": int(df.duplicated().sum()),
        "source_date_min": str(df.InvoiceDate.min()),
        "source_date_max": str(df.InvoiceDate.max()),
        "positive_purchase_rows": k[0],
        "positive_value_gbp": k[1],
        "identified_positive_value_share": identified / k[1],
        "customers": n_customer,
        "sql_pandas_sales_reconcile": bool(
            np.isclose(k[1], independent, atol=0.01, rtol=0)
        ),
        "cohort_age_zero_equals_size": bool(
            (cohorts.loc[cohorts.age_month == 0, "retention"] == 1).all()
        ),
        "cohort_rates_bounded": bool(cohorts.retention.between(0, 1).all()),
        "no_unobserved_cohort_cells": bool(
            all(
                (
                    pd.Timestamp(r.cohort) + pd.DateOffset(months=int(r.age_month))
                    < pd.Timestamp("2011-12-01")
                    for r in cohorts.itertuples()
                )
            )
        ),
        "temporal_holdout_separated": bool(
            features.loc[
                features.snapshot < pd.Timestamp("2011-11-01"), "snapshot"
            ].max()
            + pd.DateOffset(months=1)
            <= pd.Timestamp("2011-11-01")
        ),
    }
    for check in [
        "sql_pandas_sales_reconcile",
        "cohort_age_zero_equals_size",
        "cohort_rates_bounded",
        "no_unobserved_cohort_cells",
        "temporal_holdout_separated",
    ]:
        assert checks[check], check
    save_json("quality_checks.json", checks)
    plot_results(cohorts, lift, metrics, monthly, seg)
    summary = {
        "positive_value_gbp": k[1],
        "customers": n_customer,
        "weighted_month_one_retention": weighted_retention,
        **metrics,
    }
    save_json("summary.json", summary)
    report(
        "Retail retention and repeat-purchase targeting",
        "UCI Online Retail · December 2010-November 2011 · SQL cohorts and an out-of-time Python benchmark",
        [
            ("Purchase value", f"£{k[1] / 1000000.0:.2f}M"),
            ("Identified customers", f"{n_customer:,}"),
            ("Month-one retention", f"{weighted_retention:.1%}"),
            ("Top-20% holdout lift", f"{metrics['top_20pct_lift']:.2f}×"),
        ],
        [
            (
                "Decision to support",
                "Choose which existing customers to include in a measured repeat-purchase campaign. Establish customer coverage and retention before suggesting discounts.",
            ),
            (
                "Findings",
                f"The full-month window contains £{k[1]:,.0f} of positive purchase value. Identified customers account for {identified / k[1]:.1%} of that value. Across cohorts with a full next month, weighted month-one repeat purchasing is {weighted_retention:.1%}. The November model ranks a top fifth with {metrics['top_20pct_lift']:.2f} times the holdout purchase rate; a simple recency ranking reaches {metrics['recency_rule_top20_lift']:.2f} times.",
            ),
            (
                "Method",
                "DuckDB builds invoice-line, customer-order and RFM tables. Cohorts use first observed purchase and count a customer once per active month. Missing mature cells are zero-filled; future cells remain blank. Logistic regression uses log-transformed recency, frequency, monetary value and tenure from August-October snapshots. November is held out. All features precede their snapshot.",
            ),
            (
                "Recommended experiment",
                "Compare model targeting with the recency rule and a randomized no-contact control. Measure incremental repeat purchases and contribution margin after promotion costs. High propensity is not evidence that a customer needs an incentive; reserve treatment decisions for the experiment.",
            ),
            (
                "Limits and data decisions",
                "The dataset is historical and includes wholesalers. First observed purchase is not verified acquisition. Missing customer IDs remain in sales analysis but cannot enter retention or modeling. Identical source lines are retained because no line-level key proves duplication. Cancellation/negative lines are excluded from propensity features and reported separately in signed totals. December 2011 is partial and excluded. Purchase value includes all positive-priced invoice items and is neither profit nor audited net revenue. One seasonal holdout does not establish generalization.",
            ),
        ],
        [
            (
                "01_sales.png",
                "GBP values from source invoice lines. December 2011 is excluded.",
            ),
            (
                "02_cohorts.png",
                "Blank cells are not yet observable. Month 0 is 100%; color scale caps at 60% to reveal later-month variation.",
            ),
            (
                "03_segments.png",
                "Segment rules are explicit SQL thresholds, not discovered psychological customer types.",
            ),
            (
                "04_holdout.png",
                "Predictions use only information available before November. Lift measures ranking, not campaign impact.",
            ),
        ],
        [
            (
                "Holdout model metrics",
                pd.DataFrame([metrics])
                .T.reset_index()
                .rename(columns={"index": "metric", 0: "value"}),
            )
        ],
    )
    con.close()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
