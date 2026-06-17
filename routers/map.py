from fastapi import APIRouter
from fastapi.responses import JSONResponse
import json, os

router = APIRouter(prefix="/map", tags=["map"])

@router.get("/{floor}")
def get_map(floor: int):
    # План конкретного этажа: floor_plan_<floor>.json, иначе общий floor_plan.json.
    # Так можно завести разные планы по этажам, не ломая обратную совместимость.
    candidates = [f"floor_plan_{floor}.json", "floor_plan.json"]
    path = next((p for p in candidates if os.path.exists(p)), None)
    if path is None:
        return JSONResponse({"error": "План этажа не найден"}, 404)
    with open(path) as f:
        plan = json.load(f)
    plan["floor"] = floor
    return plan