"""SQLite connection helper."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "ecommerce.db"


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with Row factory enabled."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
