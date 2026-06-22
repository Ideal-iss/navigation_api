from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import json, os

router = APIRouter(prefix="/map", tags=["map"])

@router.get("/{floor}")
def get_map(floor: int, request: Request):
    candidates = [f"floor_plan_{floor}.json", "floor_plan.json"]
    path = next((p for p in candidates if os.path.exists(p)), None)
    if path is None:
        return JSONResponse({"error": "План этажа не найден"}, 404)
    with open(path) as f:
        plan = json.load(f)
    plan["floor"] = floor
    # Attach image URL if an uploaded floor plan image exists
    for ext in ("png", "jpg", "jpeg", "svg", "webp"):
        if os.path.exists(f"floor_plan_{floor}.{ext}"):
            base = str(request.base_url).rstrip("/")
            plan["image_url"] = f"{base}/admin/floor-plan/{floor}/image"
            break
    return plan