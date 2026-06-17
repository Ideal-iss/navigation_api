from fastapi import APIRouter, HTTPException
from database import db_session
from models import RouteRequest, RouteOut, NodeOut
from pathfinding import build_graph, find_route

router = APIRouter(prefix="/route", tags=["route"])

@router.get("/nodes/", response_model=list[NodeOut])
def get_nodes(floor: int = 1):
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM nodes WHERE floor=?", (floor,)).fetchall()
    return [dict(r) for r in rows]

@router.post("/", response_model=RouteOut)
def get_route(req: RouteRequest):
    # Загружаем ВСЕ узлы и рёбра: маршрут может проходить через несколько этажей
    # (через лестницы/лифты, заданные рёбрами). Раньше брался один этаж, а рёбра —
    # все подряд, из-за чего рёбра соседних этажей ломали граф.
    with db_session() as conn:
        all_nodes = conn.execute("SELECT * FROM nodes").fetchall()
        floor_nodes = conn.execute(
            "SELECT * FROM nodes WHERE floor=?", (req.floor,)
        ).fetchall()
        edges = conn.execute("SELECT * FROM edges").fetchall()

    if not floor_nodes:
        raise HTTPException(404, "Граф для этого этажа не найден")

    # Полный граф (все этажи); build_graph добавит только корректные рёбра.
    G = build_graph(all_nodes, edges)

    try:
        path, dist = find_route(G, req.from_node, req.to_node)
    except Exception as e:
        raise HTTPException(400, str(e))

    return RouteOut(nodes=path, total_distance=round(dist, 2))