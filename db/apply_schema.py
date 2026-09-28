"""
db/apply_schema.py

Applies db/schema.sql against the database in config.DB_DSN. Uses
psycopg directly instead of shelling out to `psql`, so it works even on
machines that only installed the Python driver and not the Postgres
client tools.

Safe to re-run: schema.sql uses CREATE EXTENSION IF NOT EXISTS and
CREATE TABLE IF NOT EXISTS throughout.

Usage:
    python -m db.apply_schema
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from db.connection import get_connection

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def apply_schema() -> None:
    sql = SCHEMA_PATH.read_text()
    print(f"Applying {SCHEMA_PATH} ...")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print("Schema applied successfully.")


if __name__ == "__main__":
    apply_schema()