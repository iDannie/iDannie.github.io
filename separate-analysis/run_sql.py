"""Load source tables and run SQL; no analytical calculations occur in this runner."""

import argparse
import duckdb
from support import ROOT, load_source, finish

TABLES = {
    "retail": ["monthly", "cohorts", "segments", "products", "countries", "quality"],
    "taxi": [
        "daily",
        "hourly",
        "zones",
        "routes",
        "payments",
        "forecast",
        "forecast_metrics",
        "quality",
    ],
    "complaints": [
        "monthly",
        "issues",
        "channels",
        "responses",
        "forwarding",
        "quality",
    ],
}


def main(project):
    data, zones = load_source(project)
    with duckdb.connect() as db:
        db.register("source_data", data)
        if zones is not None:
            db.register("source_zones", zones)
        db.execute((ROOT / "sql" / project / "analysis.sql").read_text())
        checks = {
            name: bool(passed)
            for name, passed in db.execute("SELECT * FROM validation").fetchall()
        }
        tables = {
            name: db.sql(f"SELECT * FROM {name}").df() for name in TABLES[project]
        }
        finish(project, "sql", tables, checks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("project", choices=TABLES)
    main(parser.parse_args().project)
