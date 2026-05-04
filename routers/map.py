from fastapi import APIRouter
from fastapi.responses import JSONResponse
import json, os

router = APIRouter(prefix="/map", tags=["map"])

@router.get("/{floor}")
def get_map(floor: int):
    path = "floor_plan.json"
    if not os.path.exists(path):
        return JSONResponse({"error": "floor_plan.json не найден"}, 404)
    with open(path) as f:
        plan = json.load(f)
    plan["floor"] = floor
    return plan