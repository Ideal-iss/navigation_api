"""
Аналитика перемещений: запись истории позиций и агрегированные отчёты.

Запись происходит автоматически через position.py при каждом успешном
определении позиции.
"""
import os
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Header
from database import db_session

ADMIN_KEY = os.getenv("ADMIN_KEY", "changeme")

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _check_admin(key: str):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Неверный admin-ключ")


def record_position(session_id: Optional[str], x: float, y: float,
                    floor: int, accuracy: float, method: Optional[str]):
    """Вызывается из position.py после успешного позиционирования."""
    with db_session() as conn:
        conn.execute(
            """INSERT INTO position_history
               (session_id, x, y, floor, accuracy, method, ts)
               VALUES (?,?,?,?,?,?,?)""",
            (session_id, round(x, 2), round(y, 2), floor,
             round(accuracy, 2), method, time.time()),
        )
        conn.commit()


@router.get("/history/")
def get_history(
    floor: Optional[int] = None,
    limit: int = 200,
    x_admin_key: str = Header(default=""),
):
    """
    Последние `limit` записей позиций (до 1000).
    Поддерживает фильтр по этажу.
    """
    _check_admin(x_admin_key)
    limit = min(limit, 1000)
    with db_session() as conn:
        if floor is not None:
            rows = conn.execute(
                "SELECT * FROM position_history WHERE floor=? ORDER BY ts DESC LIMIT ?",
                (floor, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM position_history ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


@router.get("/summary/")
def get_summary(x_admin_key: str = Header(default="")):
    """
    Сводка потоков: кол-во записей по этажам, топ-5 зон (1×1 м сетка),
    активные сессии за последний час.
    """
    _check_admin(x_admin_key)
    with db_session() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM position_history"
        ).fetchone()[0]

        by_floor = [
            dict(r) for r in conn.execute(
                "SELECT floor, COUNT(*) as cnt FROM position_history GROUP BY floor ORDER BY cnt DESC"
            ).fetchall()
        ]

        # Сетка 1×1 м — топ-5 горячих зон
        hotspots = [
            dict(r) for r in conn.execute(
                """SELECT CAST(x AS INT) as gx, CAST(y AS INT) as gy, floor,
                          COUNT(*) as visits
                   FROM position_history
                   GROUP BY gx, gy, floor
                   ORDER BY visits DESC
                   LIMIT 5"""
            ).fetchall()
        ]

        # Уникальные сессии за последний час
        since = time.time() - 3600
        active = conn.execute(
            "SELECT COUNT(DISTINCT session_id) FROM position_history WHERE ts > ?",
            (since,),
        ).fetchone()[0]

    return {
        "total_records": total,
        "by_floor": by_floor,
        "hotspots": hotspots,
        "active_sessions_1h": active,
    }


@router.delete("/history/")
def clear_history(x_admin_key: str = Header(default="")):
    """Очистить всю историю (необратимо)."""
    _check_admin(x_admin_key)
    with db_session() as conn:
        conn.execute("DELETE FROM position_history")
        conn.commit()
    return {"ok": True, "deleted": "all"}
