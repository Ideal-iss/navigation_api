from fastapi import APIRouter, HTTPException
from database import db_session
from models import PositionRequest, PositionOut
from positioning import estimate_position, DEFAULT_PATH_LOSS_N
from routers.analytics import record_position

router = APIRouter(prefix="/position", tags=["position"])


@router.post("/", response_model=PositionOut)
def get_position(req: PositionRequest):
    """
    Определение позиции по RSSI маячков.

    Метод: лог-дистанционная модель затухания (RSSI->расстояние) + мультилатерация
    методом наименьших квадратов при >=3 видимых маячках. При <3 маячках
    используется взвешенный центроид (запасной вариант). RSSI сглаживается
    EMA-фильтром для уменьшения дрожания. Возвращается оценка неопределённости.

    Формат запроса/ответа обратно совместим: добавлены только необязательные поля.
    """
    if not req.readings:
        raise HTTPException(400, "Нет показаний маячков")

    minors = list(req.readings.keys())
    placeholders = ",".join("?" * len(minors))
    with db_session() as conn:
        rows = conn.execute(
            f"SELECT * FROM beacons WHERE minor IN ({placeholders})", minors
        ).fetchall()
    beacons = [dict(r) for r in rows]

    if not beacons:
        raise HTTPException(404, "Маячки не найдены в базе данных")

    n = req.path_loss_n if req.path_loss_n is not None else DEFAULT_PATH_LOSS_N
    smoothing = True if req.smoothing is None else req.smoothing

    result = estimate_position(
        beacons=beacons,
        readings=req.readings,
        path_loss_n=n,
        smoothing=smoothing,
        session_id=req.session_id,
    )
    if result is None:
        raise HTTPException(404, "Маячки не найдены в базе данных")

    # Пишем в историю асинхронно (не блокируем ответ)
    try:
        record_position(
            session_id=req.session_id,
            x=result["x"], y=result["y"],
            floor=result["floor"], accuracy=result["accuracy"],
            method=result.get("method"),
        )
    except Exception:
        pass  # запись истории не должна ломать позиционирование

    return PositionOut(**result)
