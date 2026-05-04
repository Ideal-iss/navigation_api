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
    # Координаты по реальному плану: здание 21.5 × 14.8 м
    # (0,0) = верхний левый угол, x → вправо, y → вниз
    beacons = [
        # minor, major, mac, name, x, y, floor, tx_power
        (47597, 37641, "45:C6:6A:F2:50:75", "Маячок (верх)",   10.75,  0.0,  1, -55),
        (48100, 38144, "45:C6:6A:F2:55:78", "Маячок (лево)",    0.0,   7.4,  1, -55),
        (48203, 38247, "45:C6:6A:F2:56:81", "Маячок (стык)",    3.4,   5.1,  1, -55),
        (48215, 38259, "45:C6:6A:F2:56:93", "Маячок (низ)",    10.75, 14.8,  1, -55),
        (48596, 38640, "45:C6:6A:F2:60:74", "Маячок (право)",  21.5,   7.4,  1, -55),
    ]
    cur.executemany("""
        INSERT OR IGNORE INTO beacons
        (minor, major, mac, name, x, y, floor, tx_power)
        VALUES (?,?,?,?,?,?,?,?)
    """, beacons)

def seed_graph(cur):
    # Граф навигации по реальному плану (21.5 × 14.8 м)
    # Внутренняя комната: x=0..3.4, y=0..5.1
    # Вертикальная перегородка: x=3.4, y=0..14.1
    # Горизонтальная перегородка: y=5.1, x=3.4..9.0
    nodes = [
        # id,              name,                x,     y,    floor
        ("small_room",  "Комната",              1.7,   2.5,  1),
        ("junction",    "Перекрёсток",          3.4,   5.1,  1),
        ("corr_a",      "Коридор А",            7.0,   5.1,  1),
        ("hall_left",   "Зал (левый)",          7.0,   7.4,  1),
        ("hall_center", "Зал (центр)",         12.0,   7.4,  1),
        ("hall_right",  "Зал (правый)",        19.0,   7.4,  1),
        ("hall_bottom", "Зал (низ)",           12.0,  12.5,  1),
    ]
    cur.executemany("""
        INSERT OR IGNORE INTO nodes (id, name, x, y, floor)
        VALUES (?,?,?,?,?)
    """, nodes)

    import math
    def dist(x1, y1, x2, y2):
        return round(math.sqrt((x2-x1)**2 + (y2-y1)**2), 1)

    edges = [
        ("small_room",  "junction",    dist(1.7, 2.5,  3.4,  5.1)),  # 3.1
        ("junction",    "corr_a",      dist(3.4, 5.1,  7.0,  5.1)),  # 3.6
        ("corr_a",      "hall_left",   dist(7.0, 5.1,  7.0,  7.4)),  # 2.3
        ("hall_left",   "hall_center", dist(7.0, 7.4, 12.0,  7.4)),  # 5.0
        ("hall_center", "hall_right",  dist(12.0,7.4, 19.0,  7.4)),  # 7.0
        ("hall_left",   "hall_bottom", dist(7.0, 7.4, 12.0, 12.5)),  # 7.1
        ("hall_center", "hall_bottom", dist(12.0,7.4, 12.0, 12.5)),  # 5.1
        ("hall_right",  "hall_bottom", dist(19.0,7.4, 12.0, 12.5)),  # 8.7
    ]
    cur.executemany("""
        INSERT OR IGNORE INTO edges (from_id, to_id, weight)
        VALUES (?,?,?)
    """, edges)

def reset_graph(conn):
    cur = conn.cursor()
    cur.execute("DELETE FROM edges")
    cur.execute("DELETE FROM nodes")
    conn.commit()
    seed_graph(cur)
    conn.commit()