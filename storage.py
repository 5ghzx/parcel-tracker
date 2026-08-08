"""Local SQLite storage. No cloud, no accounts, no ads."""
import sqlite3
import os
import time

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parcels.db")


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.execute("PRAGMA foreign_keys = ON")
    return c


def init_db():
    c = _conn()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS parcels (
            number TEXT PRIMARY KEY,
            carrier INTEGER,
            carrier_name TEXT,
            label TEXT,
            last_status TEXT,
            last_status_time TEXT,
            last_checked REAL,
            archived INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT,
            time_iso TEXT,
            location_text TEXT,
            status_text TEXT,
            lat REAL,
            lon REAL,
            FOREIGN KEY(number) REFERENCES parcels(number)
        );
        CREATE TABLE IF NOT EXISTS geocache (
            query TEXT PRIMARY KEY,
            lat REAL,
            lon REAL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    c.commit()
    c.close()


def get_setting(key, default=None):
    c = _conn()
    row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    c.close()
    return row[0] if row else default


def set_setting(key, value):
    c = _conn()
    c.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    c.commit()
    c.close()


def add_parcel(number, carrier=None, label=""):
    c = _conn()
    c.execute(
        "INSERT OR IGNORE INTO parcels(number, carrier, label, last_checked) VALUES (?,?,?,0)",
        (number, carrier, label),
    )
    c.commit()
    c.close()


def remove_parcel(number):
    c = _conn()
    c.execute("DELETE FROM events WHERE number=?", (number,))
    c.execute("DELETE FROM parcels WHERE number=?", (number,))
    c.commit()
    c.close()


def list_parcels(include_archived=False):
    c = _conn()
    q = "SELECT number, carrier, carrier_name, label, last_status, last_status_time, last_checked FROM parcels"
    if not include_archived:
        q += " WHERE archived=0"
    q += " ORDER BY last_checked DESC"
    rows = c.execute(q).fetchall()
    c.close()
    cols = ["number", "carrier", "carrier_name", "label", "last_status", "last_status_time", "last_checked"]
    return [dict(zip(cols, r)) for r in rows]


def update_parcel_status(number, carrier_name, status, status_time):
    c = _conn()
    c.execute(
        "UPDATE parcels SET carrier_name=?, last_status=?, last_status_time=?, last_checked=? WHERE number=?",
        (carrier_name, status, status_time, time.time(), number),
    )
    c.commit()
    c.close()


def replace_events(number, events):
    """events: list of dicts with time_iso, location_text, status_text, lat, lon"""
    c = _conn()
    c.execute("DELETE FROM events WHERE number=?", (number,))
    c.executemany(
        "INSERT INTO events(number, time_iso, location_text, status_text, lat, lon) "
        "VALUES (:number, :time_iso, :location_text, :status_text, :lat, :lon)",
        [{**e, "number": number} for e in events],
    )
    c.commit()
    c.close()


def get_events(number):
    c = _conn()
    rows = c.execute(
        "SELECT time_iso, location_text, status_text, lat, lon FROM events "
        "WHERE number=? ORDER BY time_iso ASC",
        (number,),
    ).fetchall()
    c.close()
    cols = ["time_iso", "location_text", "status_text", "lat", "lon"]
    return [dict(zip(cols, r)) for r in rows]


def geocache_get(query):
    c = _conn()
    row = c.execute("SELECT lat, lon FROM geocache WHERE query=?", (query,)).fetchone()
    c.close()
    return (row[0], row[1]) if row else None


def geocache_set(query, lat, lon):
    c = _conn()
    c.execute(
        "INSERT OR REPLACE INTO geocache(query, lat, lon) VALUES (?,?,?)", (query, lat, lon)
    )
    c.commit()
    c.close()
