from fastapi import APIRouter, HTTPException
from database import get_db
from models import PositionRequest, PositionOut
from positioning import estimate_position, DEFAULT_PATH_LOSS_N

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

    conn = get_db()
    beacons = []
    for minor in req.readings.keys():
        row = conn.execute("SELECT * FROM beacons WHERE minor=?", (minor,)).fetchone()
        if row:
            beacons.append(dict(row))
    conn.close()

    if not beacons:
        raise HTTPException(404, "Маячки не найдены в базе данных")

    n = req.path_loss_n if req.path_loss_n is not None else DEFAULT_PATH_LOSS_N
    smoothing = True if req.smoothing is None else req.smoothing

    result = estimate_position(
        beacons=beacons,
        readings=req.readings,
        path_loss_n=n,
        smoothing=smoothing,
    )
    if result is None:
        raise HTTPException(404, "Маячки не найдены в базе данных")

    return PositionOut(**result)
