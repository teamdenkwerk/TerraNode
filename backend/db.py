"""
backend/db.py

Re-exports db.connection.get_connection so router modules can do
`from backend.db import get_connection` without reaching two levels up
into the project-root db/ package directly. Same connection, same DSN
(config.DB_DSN) as the offline pipeline — the API reads whatever the
pipeline last wrote.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from db.connection import get_connection

__all__ = ["get_connection"]