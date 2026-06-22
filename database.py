import sqlite3, math
from contextlib import contextmanager

import os
DB_PATH = os.getenv("DB_PATH", "/data/navigation.db" if os.path.isdir("/data") else "navigation.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_session():
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


def _cols(conn, table: str) -> set:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _migrate(conn):
    """Migrate old schema (floor column) to new schema (floor_id column)."""
    cur = conn.cursor()

    if "beacons" in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}:
        cols = _cols(conn, "beacons")
        if "floor" in cols and "floor_id" not in cols:
            cur.execute("ALTER TABLE beacons ADD COLUMN floor_id INTEGER DEFAULT 1")
            cur.execute("UPDATE beacons SET floor_id = floor")
            conn.commit()

    if "nodes" in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}:
        cols = _cols(conn, "nodes")
        if "floor" in cols and "floor_id" not in cols:
            cur.execute("ALTER TABLE nodes ADD COLUMN floor_id INTEGER DEFAULT 1")
            cur.execute("UPDATE nodes SET floor_id = floor")
            conn.commit()


def init_db():
    conn = get_db()
    _migrate(conn)  # run before CREATE IF NOT EXISTS so new code sees floor_id
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS buildings (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT NOT NULL,
            address TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS floors (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id   INTEGER REFERENCES buildings(id),
            level_number  INTEGER NOT NULL DEFAULT 1,
            map_image_url TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT,
            description TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            description TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            full_name     TEXT,
            role_id       INTEGER REFERENCES roles(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS beacons (
            minor               INTEGER PRIMARY KEY,
            major               INTEGER,
            mac                 TEXT,
            name                TEXT,
            x                   REAL DEFAULT 0,
            y                   REAL DEFAULT 0,
            floor_id            INTEGER DEFAULT 1,
            tx_power            INTEGER DEFAULT -55,
            last_battery_change DATE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id       TEXT PRIMARY KEY,
            name     TEXT,
            x        REAL DEFAULT 0,
            y        REAL DEFAULT 0,
            floor_id INTEGER DEFAULT 1,
            room_id  INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS edges (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id TEXT,
            to_id   TEXT,
            weight  REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS position_history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            x          REAL,
            y          REAL,
            floor      INTEGER DEFAULT 1,
            accuracy   REAL,
            method     TEXT,
            ts         REAL DEFAULT (julianday('now') * 86400.0)
        )
    """)

    conn.commit()

    # Seed default building + floor if DB is fresh
    cur.execute("SELECT COUNT(*) FROM buildings")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO buildings (name, address) VALUES ('Главный корпус', 'Ул. Примерная, 1')"
        )
        building_id = cur.lastrowid
        cur.execute(
            "INSERT INTO floors (building_id, level_number) VALUES (?, 1)", (building_id,)
        )
        conn.commit()

    cur.execute("SELECT COUNT(*) FROM beacons")
    if cur.fetchone()[0] == 0:
        seed_beacons(cur)
        conn.commit()

    cur.execute("SELECT COUNT(*) FROM nodes")
    if cur.fetchone()[0] == 0:
        seed_graph(cur)
        conn.commit()

    conn.close()


def seed_beacons(cur):
    beacons = [
        (47597, 37641, "45:C6:6A:F2:50:75", "Маячок (верх)",   10.75,  0.0,  1, -55),
        (48100, 38144, "45:C6:6A:F2:55:78", "Маячок (лево)",    0.0,   7.4,  1, -55),
        (48203, 38247, "45:C6:6A:F2:56:81", "Маячок (стык)",    3.4,   5.1,  1, -55),
        (48215, 38259, "45:C6:6A:F2:56:93", "Маячок (низ)",    10.75, 13.5,  1, -55),
        (48596, 38640, "45:C6:6A:F2:60:74", "Маячок (право)",  21.5,   7.4,  1, -55),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO beacons (minor, major, mac, name, x, y, floor_id, tx_power)"
        " VALUES (?,?,?,?,?,?,?,?)",
        beacons,
    )


def seed_graph(cur):
    nodes = [
        ("small_room",  "Комната",          1.7,  2.5, 1),
        ("junction",    "Перекрёсток",       3.4,  5.1, 1),
        ("corr_a",      "Коридор А",         7.0,  5.1, 1),
        ("hall_left",   "Зал (левый)",       7.0,  7.4, 1),
        ("hall_center", "Зал (центр)",      12.0,  7.4, 1),
        ("hall_right",  "Зал (правый)",     19.0,  7.4, 1),
        ("hall_bottom", "Зал (низ)",        12.0, 12.5, 1),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO nodes (id, name, x, y, floor_id) VALUES (?,?,?,?,?)",
        nodes,
    )

    def d(x1, y1, x2, y2):
        return round(math.hypot(x2 - x1, y2 - y1), 1)

    edges = [
        ("small_room",  "junction",    d(1.7, 2.5,  3.4,  5.1)),
        ("junction",    "corr_a",      d(3.4, 5.1,  7.0,  5.1)),
        ("corr_a",      "hall_left",   d(7.0, 5.1,  7.0,  7.4)),
        ("hall_left",   "hall_center", d(7.0, 7.4, 12.0,  7.4)),
        ("hall_center", "hall_right",  d(12.0,7.4, 19.0,  7.4)),
        ("hall_left",   "hall_bottom", d(7.0, 7.4, 12.0, 12.5)),
        ("hall_center", "hall_bottom", d(12.0,7.4, 12.0, 12.5)),
        ("hall_right",  "hall_bottom", d(19.0,7.4, 12.0, 12.5)),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO edges (from_id, to_id, weight) VALUES (?,?,?)",
        edges,
    )


def reset_graph(conn):
    cur = conn.cursor()
    cur.execute("DELETE FROM edges")
    cur.execute("DELETE FROM nodes")
    conn.commit()
    seed_graph(cur)
    conn.commit()
