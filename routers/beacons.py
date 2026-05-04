from fastapi import APIRouter, HTTPException
from database import get_db
from models import BeaconOut, BeaconUpdate, BeaconCreate

router = APIRouter(prefix="/beacons", tags=["beacons"])

@router.get("/", response_model=list[BeaconOut])
def get_beacons(floor: int = None):
    conn = get_db()
    if floor:
        rows = conn.execute("SELECT * FROM beacons WHERE floor=?", (floor,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM beacons").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/{minor}", response_model=BeaconOut)
def get_beacon(minor: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM beacons WHERE minor=?", (minor,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, f"Маячок {minor} не найден")
    return dict(row)

@router.post("/", response_model=BeaconOut)
def create_beacon(data: BeaconCreate):
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO beacons (minor, major, mac, name, x, y, floor, tx_power)
            VALUES (?,?,?,?,?,?,?,?)
        """, (data.minor, data.major, data.mac, data.name,
              data.x, data.y, data.floor, data.tx_power))
        conn.commit()
        row = conn.execute("SELECT * FROM beacons WHERE minor=?", (data.minor,)).fetchone()
        return dict(row)
    except Exception as e:
        raise HTTPException(400, f"Ошибка: {e}")
    finally:
        conn.close()

@router.patch("/{minor}", response_model=BeaconOut)
def update_beacon(minor: int, data: BeaconUpdate):
    conn = get_db()
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "Нет данных для обновления")
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(
        f"UPDATE beacons SET {sets} WHERE minor=?",
        (*fields.values(), minor)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM beacons WHERE minor=?", (minor,)).fetchone()
    conn.close()
    return dict(row)

@router.delete("/{minor}")
def delete_beacon(minor: int):
    conn = get_db()
    conn.execute("DELETE FROM beacons WHERE minor=?", (minor,))
    conn.commit()
    conn.close()
    return {"ok": True, "deleted": minor}
