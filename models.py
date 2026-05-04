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

class PositionOut(BaseModel):
    x:        float
    y:        float
    floor:    int
    accuracy: float

class RouteRequest(BaseModel):
    from_node: str
    to_node:   str
    floor:     int = 1

class RouteOut(BaseModel):
    nodes:          list[str]
    total_distance: float

class NodeOut(BaseModel):
    id:    str
    name:  str
    x:     float
    y:     float
    floor: int
