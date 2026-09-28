"""
db/connection.py

Thin wrapper around psycopg3 so every other module does
`from db.connection import get_connection` and never touches the DSN
directly. Uses dict_row so query results come back as dicts (matches
what matching/reconciliation/verification modules expect).
"""

import psycopg
from psycopg.rows import dict_row

from config import DB_DSN


def get_connection():
    """Returns a context-manager connection with dict-row results and
    autocommit off (explicit commit on successful `with` exit, matching
    psycopg3's default transactional behavior)."""
    return psycopg.connect(DB_DSN, row_factory=dict_row)