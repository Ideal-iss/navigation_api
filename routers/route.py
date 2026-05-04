from fastapi import APIRouter, HTTPException
from database import get_db
from models import RouteRequest, RouteOut
from pathfinding import build_graph, find_route

router = APIRouter(prefix="/route", tags=["route"])

@router.post("/", response_model=RouteOut)
def get_route(req: RouteRequest):
    conn = get_db()
    nodes = conn.execute(
        "SELECT * FROM nodes WHERE floor=?", (req.floor,)
    ).fetchall()
    edges = conn.execute("SELECT * FROM edges").fetchall()
    conn.close()

    if not nodes:
        raise HTTPException(404, "Граф для этого этажа не найден")

    G = build_graph(nodes, edges)

    try:
        path, dist = find_route(G, req.from_node, req.to_node)
    except Exception as e:
        raise HTTPException(400, str(e))

    return RouteOut(nodes=path, total_distance=round(dist, 2))