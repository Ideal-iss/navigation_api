from fastapi import APIRouter, HTTPException
from database import get_db
from models import PositionRequest, PositionOut

router = APIRouter(prefix="/position", tags=["position"])

@router.post("/", response_model=PositionOut)
def get_position(req: PositionRequest):
    if not req.readings:
        raise HTTPException(400, "Нет показаний маячков")

    conn = get_db()
    points = []
    for minor, rssi in req.readings.items():
        row = conn.execute("SELECT * FROM beacons WHERE minor=?", (minor,)).fetchone()
        if row:
            b = dict(row)
            ratio = (b["tx_power"] - rssi) / (10.0 * 2.0)
            distance = max(10.0 ** ratio, 0.1)
            points.append((b["x"], b["y"], b["floor"], distance))
    conn.close()

    if not points:
        raise HTTPException(404, "Маячки не найдены в базе данных")

    # Weighted centroid: weight = 1/d^2
    weights = [1.0 / (d ** 2) for _, _, _, d in points]
    total = sum(weights)
    x = sum(w * px for w, (px, _, _, _) in zip(weights, points)) / total
    y = sum(w * py for w, (_, py, _, _) in zip(weights, points)) / total

    # Floor: этаж ближайшего маячка
    floor = min(points, key=lambda p: p[3])[2]

    # Accuracy: взвешенное среднее расстояние (чем меньше — тем точнее)
    accuracy = sum(w * d for w, (_, _, _, d) in zip(weights, points)) / total

    return PositionOut(x=round(x, 2), y=round(y, 2), floor=floor, accuracy=round(accuracy, 2))
