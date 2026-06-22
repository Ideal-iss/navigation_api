from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import db_session

router = APIRouter(prefix="/rooms", tags=["rooms"])


class RoomCreate(BaseModel):
    name: str
    description: Optional[str] = None


class RoomUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


@router.get("/")
def list_rooms():
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM rooms ORDER BY name").fetchall()
    return [dict(r) for r in rows]


@router.post("/", status_code=201)
def create_room(data: RoomCreate):
    with db_session() as conn:
        cur = conn.execute(
            "INSERT INTO rooms (name, description) VALUES (?,?)",
            (data.name, data.description)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM rooms WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)


@router.patch("/{room_id}")
def update_room(room_id: int, data: RoomUpdate):
    raw = data.model_dump(exclude_unset=True)
    if not raw:
        raise HTTPException(400, "Нет данных")
    sets = ", ".join(f"{k}=?" for k in raw)
    with db_session() as conn:
        conn.execute(f"UPDATE rooms SET {sets} WHERE id=?", (*raw.values(), room_id))
        conn.commit()
        row = conn.execute("SELECT * FROM rooms WHERE id=?", (room_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Комната не найдена")
    return dict(row)


@router.delete("/{room_id}")
def delete_room(room_id: int):
    with db_session() as conn:
        conn.execute("UPDATE nodes SET room_id=NULL WHERE room_id=?", (room_id,))
        conn.execute("DELETE FROM rooms WHERE id=?", (room_id,))
        conn.commit()
    return {"ok": True}
