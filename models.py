from pydantic import BaseModel
from typing import Optional

class BeaconCreate(BaseModel):
    minor:    int
    major:    int
    mac:      str
    name:     str
    x:        float = 0.0
    y:        float = 0.0
    floor:    int   = 1
    tx_power: int   = -55

class BeaconUpdate(BaseModel):
    name:     Optional[str]   = None
    x:        Optional[float] = None
    y:        Optional[float] = None
    floor:    Optional[int]   = None
    tx_power: Optional[int]   = None

class BeaconOut(BaseModel):
    minor:    int
    major:    int
    mac:      str
    name:     str
    x:        float
    y:        float
    floor:    int
    tx_power: int

class PositionRequest(BaseModel):
    readings: dict[int, int]
    # Дополнительные (необязательные) параметры — обратно совместимо.
    path_loss_n: Optional[float] = None  # показатель затухания среды
    smoothing:   Optional[bool]  = None  # сглаживание RSSI (EMA)
    session_id:  Optional[str]   = None  # клиент/сессия для пер-сессионного EMA

class PositionOut(BaseModel):
    x:        float
    y:        float
    floor:    int
    accuracy: float
    # Новые поля — аддитивны, старые клиенты их просто игнорируют.
    method:      Optional[str]   = None  # использованный метод позиционирования
    num_beacons: Optional[int]   = None  # сколько маячков участвовало
    uncertainty: Optional[float] = None  # оценка неопределённости, м

class RouteRequest(BaseModel):
    from_node: str
    to_node:   str
    floor:     int = 1

class RoutePointRequest(BaseModel):
    """Маршрут от произвольной точки (реальной позиции) до узла."""
    x:       float
    y:       float
    to_node: str
    floor:   int = 1

class RouteOut(BaseModel):
    nodes:          list[str]
    total_distance: float
    # Реальная стартовая точка (если маршрут строился от координат, а не узла).
    # Клиент рисует первый сегмент от неё к первому узлу — без «прыжка» к графу.
    start_x: Optional[float] = None
    start_y: Optional[float] = None

class NodeOut(BaseModel):
    id:      str
    name:    str
    x:       float
    y:       float
    floor:   int
    room_id: Optional[int] = None

class NodeCreate(BaseModel):
    id:      str
    name:    str = ""
    x:       float = 0.0
    y:       float = 0.0
    floor:   int   = 1
    room_id: Optional[int] = None

class NodeUpdate(BaseModel):
    name:    Optional[str]   = None
    x:       Optional[float] = None
    y:       Optional[float] = None
    floor:   Optional[int]   = None
    room_id: Optional[int]   = None

class EdgeCreate(BaseModel):
    from_id: str
    to_id:   str
    # weight необязателен: если не задан, считается по координатам узлов.
    weight:  Optional[float] = None

class EdgeOut(BaseModel):
    id:      int
    from_id: str
    to_id:   str
    weight:  float
