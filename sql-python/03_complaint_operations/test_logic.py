"""Protect the year boundary, missing timeliness and missing issue dimensions."""

import unittest
import duckdb, pandas as pd, numpy as np
from common import ROOT
from run import wilson


class ComplaintLogic(unittest.TestCase):
    def test_missing_labels_are_not_late_or_timely(self):
        d = pd.DataFrame(
            {
                "complaint_id": ["1", "2", "3"],
                "received": pd.to_datetime(["2024-01-01", "2024-12-31", "2025-01-01"]),
                "sent": pd.to_datetime(["2024-01-01", "2025-01-01", "2025-01-01"]),
                "product": ["Mortgage"] * 3,
                "timely": ["No", None, "Yes"],
                "issue": ["Payments", None, "Payments"],
            }
        )
        c = duckdb.connect()
        c.register("source_complaints", d)
        c.execute((ROOT / "sql/01_model.sql").read_text())
        self.assertEqual(
            c.execute(
                "SELECT count(*),count(late_response),sum(late_response) FROM complaint_fact"
            ).fetchone(),
            (2, 1, 1),
        )
        self.assertEqual(
            c.execute(
                "SELECT count(*) FROM complaint_fact WHERE issue_key IS NULL"
            ).fetchone()[0],
            0,
        )
        c.close()

    def test_wilson_extremes(self):
        low, high = wilson(np.array([0, 10]), np.array([10, 10]))
        self.assertTrue(np.all(low >= 0))
        self.assertTrue(np.all(high <= 1))
        self.assertAlmostEqual(low[0], 0)
        self.assertAlmostEqual(high[1], 1)


if __name__ == "__main__":
    unittest.main()
