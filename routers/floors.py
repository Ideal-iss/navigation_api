from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import db_session

router = APIRouter(prefix="/floors", tags=["floors"])


class FloorCreate(BaseModel):
    building_id: int = 1
    level_number: int
    map_image_url: Optional[str] = None


class FloorUpdate(BaseModel):
    level_number: Optional[int] = None
    map_image_url: Optional[str] = None


@router.get("/")
def list_floors():
    with db_session() as conn:
        rows = conn.execute("""
            SELECT f.id, f.building_id, f.level_number, f.map_image_url,
                   b.name AS building_name
            FROM floors f
            LEFT JOIN buildings b ON b.id = f.building_id
            ORDER BY f.level_number
        """).fetchall()
    return [dict(r) for r in rows]


@router.post("/", status_code=201)
def create_floor(data: FloorCreate):
    with db_session() as conn:
        exists = conn.execute(
            "SELECT 1 FROM floors WHERE building_id=? AND level_number=?",
            (data.building_id, data.level_number)
        ).fetchone()
        if exists:
            raise HTTPException(409, f"Этаж {data.level_number} уже существует")
        cur = conn.execute(
            "INSERT INTO floors (building_id, level_number, map_image_url) VALUES (?,?,?)",
            (data.building_id, data.level_number, data.map_image_url)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM floors WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)


@router.patch("/{floor_id}")
def update_floor(floor_id: int, data: FloorUpdate):
    raw = data.model_dump(exclude_unset=True)
    if not raw:
        raise HTTPException(400, "Нет данных")
    sets = ", ".join(f"{k}=?" for k in raw)
    with db_session() as conn:
        conn.execute(f"UPDATE floors SET {sets} WHERE id=?", (*raw.values(), floor_id))
        conn.commit()
        row = conn.execute("SELECT * FROM floors WHERE id=?", (floor_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Этаж не найден")
    return dict(row)


@router.delete("/{floor_id}")
def delete_floor(floor_id: int):
    with db_session() as conn:
        conn.execute("DELETE FROM floors WHERE id=?", (floor_id,))
        conn.commit()
    return {"ok": True}


@router.get("/buildings/")
def list_buildings():
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM buildings ORDER BY id").fetchall()
    return [dict(r) for r in rows]
