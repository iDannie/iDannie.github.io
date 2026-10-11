"""Compare independently computed Python and SQL aggregate result tables."""

from pathlib import Path
import json
import pandas as pd
from pandas.testing import assert_frame_equal

ROOT = Path(__file__).resolve().parent
KEYS = {
    "retail": {
        "monthly": ["month"],
        "cohorts": ["cohort", "age_month"],
        "segments": ["segment"],
        "products": ["StockCode"],
        "countries": ["country"],
        "quality": [],
    },
    "taxi": {
        "daily": ["day"],
        "hourly": ["hour"],
        "zones": ["PULocationID"],
        "routes": ["PULocationID", "DOLocationID"],
        "payments": ["payment_type"],
        "forecast": ["day"],
        "forecast_metrics": [],
        "quality": [],
    },
    "complaints": {
        "monthly": ["month"],
        "issues": ["issue"],
        "channels": ["channel"],
        "responses": ["response"],
        "forwarding": ["forwarding_days"],
        "quality": [],
    },
}


def main():
    results = {}
    for project, tables in KEYS.items():
        for name, keys in tables.items():
            frames = []
            for language in ["python", "sql"]:
                df = pd.read_csv(ROOT / language / project / "results" / f"{name}.csv")
                for col in ["month", "cohort", "day"]:
                    if col in df:
                        df[col] = pd.to_datetime(df[col])
                if keys:
                    df = df.sort_values(keys, na_position="last")
                frames.append(df.reset_index(drop=True).sort_index(axis=1))
            assert_frame_equal(
                *frames, check_dtype=False, check_exact=False, atol=1e-7, rtol=1e-10
            )
            results[f"{project}/{name}"] = {"matched": True, "rows": len(frames[0])}
    (ROOT / "verification.json").write_text(json.dumps(results, indent=2))
    print(f"{len(results)} Python/SQL result tables matched independently.")


if __name__ == "__main__":
    main()
