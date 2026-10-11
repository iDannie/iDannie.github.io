"""Small boundary fixtures complement reconciliation on the full datasets."""

import importlib.util
import unittest
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent


def python_analysis(project, *args):
    spec = importlib.util.spec_from_file_location(
        project, ROOT / "python" / project / "analysis.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.analyze(*args)[0]


def sql_analysis(project, data, zones=None):
    db = duckdb.connect()
    db.register("source_data", data)
    if zones is not None:
        db.register("source_zones", zones)
    db.execute((ROOT / "sql" / project / "analysis.sql").read_text())
    return db


class BoundaryTests(unittest.TestCase):
    def test_retail_observation_window_and_missing_customer(self):
        df = pd.DataFrame(
            {
                "InvoiceNo": ["1", "2", "3", "C4", "5"],
                "StockCode": ["A"] * 5,
                "CustomerID": ["10", "10", None, "10", "20"],
                "Country": ["UK"] * 5,
                "Quantity": [1, 1, 1, -1, 1],
                "UnitPrice": [10.0] * 5,
                "InvoiceDate": pd.to_datetime(
                    [
                        "2011-09-01",
                        "2011-11-01",
                        "2011-11-02",
                        "2011-11-03",
                        "2011-12-01",
                    ]
                ),
            }
        )
        python = python_analysis("retail", df)
        with sql_analysis("retail", df) as db:
            for tables in [
                python,
                {
                    n: db.sql(f"SELECT * FROM {n}").df()
                    for n in ["monthly", "cohorts", "quality"]
                },
            ]:
                self.assertEqual(tables["monthly"].purchase_value.sum(), 30)
                self.assertEqual(tables["monthly"].signed_value.sum(), 20)
                self.assertEqual(tables["quality"].customers.iloc[0], 1)
                cohort = tables["cohorts"]
                self.assertEqual(
                    cohort.loc[cohort.age_month == 1, "active_customers"].iloc[0], 0
                )
                self.assertEqual(cohort.age_month.max(), 2)

    def test_taxi_calendar_zero_and_holdout_separation(self):
        df = pd.DataFrame(
            {
                "PULocationID": [1, 1],
                "DOLocationID": [1, 1],
                "fare_amount": [5.0, 5.0],
                "total_amount": [6.0, 6.0],
                "tip_amount": [1.0, 1.0],
                "trip_distance": [2.0, 2.0],
                "payment_type": [1, 1],
                "tpep_pickup_datetime": pd.to_datetime(
                    ["2024-01-18 10:00", "2024-01-25 10:00"]
                ),
                "tpep_dropoff_datetime": pd.to_datetime(
                    ["2024-01-18 10:10", "2024-01-25 10:10"]
                ),
            }
        )
        zones = pd.DataFrame({"LocationID": [1], "Zone": ["Test zone"]})
        python = python_analysis("taxi", df, zones)
        with sql_analysis("taxi", df, zones) as db:
            for tables in [
                python,
                {n: db.sql(f"SELECT * FROM {n}").df() for n in ["daily", "forecast"]},
            ]:
                self.assertEqual(len(tables["daily"]), 31)
                self.assertEqual(tables["daily"].records.sum(), 2)
                self.assertEqual(
                    tables["forecast"].prediction.tolist(), [1, 0, 0, 0, 0, 0, 0]
                )

    def test_complaint_denominators_and_exclusive_end(self):
        df = pd.DataFrame(
            {
                "complaint_id": ["1", "2", "3", "4"],
                "product": ["Mortgage"] * 4,
                "received": pd.to_datetime(
                    ["2024-01-01", "2024-01-02", "2024-01-03", "2025-01-01"]
                ),
                "sent": pd.to_datetime(
                    ["2024-01-01", "2024-01-01", None, "2025-01-01"]
                ),
                "issue": ["Test"] * 4,
                "channel": ["Web"] * 4,
                "response": ["Closed"] * 4,
                "timely": ["Yes", "No", None, "No"],
            }
        )
        python = python_analysis("complaints", df)
        with sql_analysis("complaints", df) as db:
            for tables in [
                python,
                {
                    n: db.sql(f"SELECT * FROM {n}").df()
                    for n in ["quality", "issues", "monthly"]
                },
            ]:
                q = tables["quality"].iloc[0]
                self.assertEqual(q.complaints, 3)
                self.assertEqual(q.known_timeliness, 2)
                self.assertEqual(q.negative_forwarding, 1)
                self.assertEqual(q.missing_forwarding, 1)
                self.assertEqual(tables["issues"].late_rate.iloc[0], 0.5)
                self.assertEqual(len(tables["monthly"]), 12)


if __name__ == "__main__":
    unittest.main()
