import sqlite3
import json

DB_PATH = "navigation.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # Таблица маячков
    cur.execute("""
        CREATE TABLE IF NOT EXISTS beacons (
            minor     INTEGER PRIMARY KEY,
            major     INTEGER,
            mac       TEXT,
            name      TEXT,
            x         REAL,
            y         REAL,
            floor     INTEGER DEFAULT 1,
            tx_power  INTEGER DEFAULT -55
        )
    """)

    # Таблица узлов графа (коридоры, точки маршрута)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id    TEXT PRIMARY KEY,
            name  TEXT,
            x     REAL,
            y     REAL,
            floor INTEGER DEFAULT 1
        )
    """)

    # Таблица рёбер графа
    cur.execute("""
        CREATE TABLE IF NOT EXISTS edges (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id  TEXT,
            to_id    TEXT,
            weight   REAL
        )
    """)

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
        (47597, 37641, "45:C6:6A:F2:50:75", "Аудитория 101",  0.0,  0.0,  1, -55),
        (48100, 38144, "45:C6:6A:F2:55:78", "Аудитория 102", 15.0,  0.0,  1, -55),
        (48203, 38247, "45:C6:6A:F2:56:81", "Коридор",        5.0,  5.0,  1, -55),
        (48215, 38259, "45:C6:6A:F2:56:93", "Аудитория 104",  5.0, 15.0,  1, -55),
        (48596, 38640, "45:C6:6A:F2:60:74", "Аудитория 103", 10.0, 10.0,  1, -55),
    ]
    cur.executemany("""
        INSERT OR IGNORE INTO beacons
        (minor, major, mac, name, x, y, floor, tx_power)
        VALUES (?,?,?,?,?,?,?,?)
    """, beacons)

def seed_graph(cur):
    nodes = [
        ("room_101",  "Аудитория 101",  0.0,  0.0, 1),
        ("corr_1",    "Коридор 1",       5.0,  0.0, 1),
        ("corr_2",    "Коридор 2",      10.0,  0.0, 1),
        ("room_102",  "Аудитория 102",  15.0,  0.0, 1),
        ("corr_3",    "Коридор 3",       5.0,  5.0, 1),
        ("corr_4",    "Коридор 4",       5.0, 10.0, 1),
        ("room_103",  "Аудитория 103",  10.0, 10.0, 1),
        ("room_104",  "Аудитория 104",   5.0, 15.0, 1),
    ]
    cur.executemany("""
        INSERT OR IGNORE INTO nodes (id, name, x, y, floor)
        VALUES (?,?,?,?,?)
    """, nodes)

    edges = [
        ("room_101", "corr_1",  5.0),
        ("corr_1",   "corr_2",  5.0),
        ("corr_2",   "room_102", 5.0),
        ("corr_1",   "corr_3",  5.0),
        ("corr_3",   "corr_4",  5.0),
        ("corr_4",   "room_103", 5.0),
        ("corr_4",   "room_104", 5.0),
    ]
    cur.executemany("""
        INSERT OR IGNORE INTO edges (from_id, to_id, weight)
        VALUES (?,?,?)
    """, edges)