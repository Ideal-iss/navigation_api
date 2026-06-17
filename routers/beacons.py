from typing import Optional
from fastapi import APIRouter, HTTPException
from database import db_session
from models import BeaconOut, BeaconUpdate, BeaconCreate

router = APIRouter(prefix="/beacons", tags=["beacons"])

@router.get("/", response_model=list[BeaconOut])
def get_beacons(floor: Optional[int] = None):
    with db_session() as conn:
        if floor is not None:  # этаж 0 — валиден, поэтому сравниваем с None
            rows = conn.execute("SELECT * FROM beacons WHERE floor=?", (floor,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM beacons").fetchall()
    return [dict(r) for r in rows]

@router.get("/{minor}", response_model=BeaconOut)
def get_beacon(minor: int):
    with db_session() as conn:
        row = conn.execute("SELECT * FROM beacons WHERE minor=?", (minor,)).fetchone()
    if not row:
        raise HTTPException(404, f"Маячок {minor} не найден")
    return dict(row)

@router.post("/", response_model=BeaconOut)
def create_beacon(data: BeaconCreate):
    with db_session() as conn:
        try:
            conn.execute("""
                INSERT INTO beacons (minor, major, mac, name, x, y, floor, tx_power)
                VALUES (?,?,?,?,?,?,?,?)
            """, (data.minor, data.major, data.mac, data.name,
                  data.x, data.y, data.floor, data.tx_power))
            conn.commit()
        except Exception as e:
            raise HTTPException(400, f"Ошибка: {e}")
        row = conn.execute("SELECT * FROM beacons WHERE minor=?", (data.minor,)).fetchone()
    return dict(row)

@router.patch("/{minor}", response_model=BeaconOut)
def update_beacon(minor: int, data: BeaconUpdate):
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "Нет данных для обновления")
    sets = ", ".join(f"{k}=?" for k in fields)
    with db_session() as conn:
        conn.execute(
            f"UPDATE beacons SET {sets} WHERE minor=?",
            (*fields.values(), minor)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM beacons WHERE minor=?", (minor,)).fetchone()
    if not row:
        raise HTTPException(404, f"Маячок {minor} не найден")
    return dict(row)

@router.delete("/{minor}")
def delete_beacon(minor: int):
    with db_session() as conn:
        conn.execute("DELETE FROM beacons WHERE minor=?", (minor,))
        conn.commit()
    return {"ok": True, "deleted": minor}
