"""Small boundary fixtures test semantics independently of the downloaded data."""

import unittest
import duckdb, pandas as pd
from common import ROOT


class RetailLogic(unittest.TestCase):
    def test_cancellations_duplicates_missing_ids_and_boundary(self):
        rows = [
            ("A", 2, 3, "1", "2011-01-02"),
            ("A", 2, 3, "1", "2011-01-02"),
            ("C1", -1, 3, "1", "2011-01-03"),
            ("B", 1, 10, None, "2011-01-04"),
            ("Z", 1, 0, "2", "2011-01-05"),
            ("D", 1, 50, "2", "2011-12-01"),
        ]
        df = pd.DataFrame(
            rows,
            columns=["InvoiceNo", "Quantity", "UnitPrice", "CustomerID", "InvoiceDate"],
        )
        df.InvoiceDate = pd.to_datetime(df.InvoiceDate)
        c = duckdb.connect()
        c.register("source_retail", df)
        c.execute((ROOT / "sql/01_model.sql").read_text())
        self.assertEqual(
            c.execute("SELECT count(*),sum(signed_value) FROM purchases").fetchone(),
            (3, 22),
        )
        self.assertEqual(
            c.execute(
                "SELECT count(*),sum(order_value) FROM customer_orders"
            ).fetchone(),
            (1, 12),
        )
        self.assertEqual(
            c.execute("SELECT sum(signed_value) FROM lines").fetchone()[0], 19
        )
        cohorts = c.execute((ROOT / "sql/03_cohorts.sql").read_text()).df()
        self.assertEqual(cohorts.loc[cohorts.age_month == 0, "retention"].iloc[0], 1)
        self.assertEqual(cohorts.loc[cohorts.age_month == 1, "retention"].iloc[0], 0)
        c.close()


if __name__ == "__main__":
    unittest.main()
