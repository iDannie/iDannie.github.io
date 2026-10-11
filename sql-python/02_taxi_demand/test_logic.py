"""Check filter scopes and zero-filled grids using controlled boundary records."""

import unittest
import duckdb, pandas as pd
from common import ROOT


class TaxiLogic(unittest.TestCase):
    def test_paid_demand_and_operational_scopes_differ(self):
        d = pd.DataFrame(
            {
                "tpep_pickup_datetime": pd.to_datetime(
                    ["2024-01-01"] * 4 + ["2024-02-01"]
                ),
                "tpep_dropoff_datetime": pd.to_datetime(
                    [
                        "2024-01-01 00:10",
                        "2024-01-01 00:00",
                        "2024-01-01 00:10",
                        "2024-01-01 00:10",
                        "2024-02-01 00:10",
                    ]
                ),
                "PULocationID": [1, 1, 264, 1, 1],
                "fare_amount": [10, 10, 10, -10, 10],
                "trip_distance": [2, 2, 2, 2, 2],
                "total_amount": [12, 12, 12, -12, 12],
            }
        )
        z = pd.DataFrame(
            {
                "LocationID": [1, 264],
                "Zone": ["Known", "Unknown"],
                "Borough": ["A", "Unknown"],
            }
        )
        c = duckdb.connect()
        c.register("source_trips", d)
        c.register("zones", z)
        c.execute((ROOT / "sql/01_model.sql").read_text())
        self.assertEqual(c.execute("SELECT count(*) FROM demand").fetchone()[0], 2)
        self.assertEqual(c.execute("SELECT count(*) FROM operations").fetchone()[0], 1)
        panel = c.execute((ROOT / "sql/02_hourly_panel.sql").read_text()).df()
        self.assertEqual(len(panel), 744)
        self.assertEqual(panel.records.sum(), 2)
        self.assertEqual((panel.records == 0).sum(), 743)
        c.close()


if __name__ == "__main__":
    unittest.main()
