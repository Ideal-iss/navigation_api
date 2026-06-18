import math
import networkx as nx
from fastapi import APIRouter, HTTPException
from database import db_session
from models import (
    RouteRequest, RouteOut, NodeOut, NodeCreate, NodeUpdate, EdgeCreate, EdgeOut,
)
from pathfinding import build_graph, find_route

router = APIRouter(prefix="/route", tags=["route"])


@router.get("/diagnostics/")
def graph_diagnostics(floor: int = 1):
    """
    Диагностика связности графа этажа: изолированные узлы и компоненты связности.

    Помогает находить «дыры» — узлы без рёбер и несвязанные между собой группы,
    из-за которых маршрут между некоторыми точками построить нельзя.
    """
    with db_session() as conn:
        nodes = [dict(r) for r in conn.execute(
            "SELECT * FROM nodes WHERE floor=?", (floor,)).fetchall()]
        edges = [dict(r) for r in conn.execute("SELECT * FROM edges").fetchall()]

    G = build_graph(nodes, edges)  # рёбра добавятся только между узлами этажа
    isolated = sorted(n for n in G.nodes if G.degree(n) == 0)
    components = sorted((sorted(c) for c in nx.connected_components(G)), key=len, reverse=True)
    return {
        "floor": floor,
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "isolated": isolated,
        "components": components,
        "connected": len(components) <= 1,
    }

@router.get("/nodes/", response_model=list[NodeOut])
def get_nodes(floor: int = 1):
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM nodes WHERE floor=?", (floor,)).fetchall()
    return [dict(r) for r in rows]

# ── CRUD узлов графа ─────────────────────────────────────────

@router.post("/nodes/", response_model=NodeOut)
def create_node(data: NodeCreate):
    with db_session() as conn:
        exists = conn.execute("SELECT 1 FROM nodes WHERE id=?", (data.id,)).fetchone()
        if exists:
            raise HTTPException(409, f"Узел '{data.id}' уже существует")
        conn.execute(
            "INSERT INTO nodes (id, name, x, y, floor) VALUES (?,?,?,?,?)",
            (data.id, data.name, data.x, data.y, data.floor),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM nodes WHERE id=?", (data.id,)).fetchone()
    return dict(row)

@router.patch("/nodes/{node_id}", response_model=NodeOut)
def update_node(node_id: str, data: NodeUpdate):
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "Нет данных для обновления")
    sets = ", ".join(f"{k}=?" for k in fields)
    with db_session() as conn:
        conn.execute(f"UPDATE nodes SET {sets} WHERE id=?", (*fields.values(), node_id))
        conn.commit()
        row = conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
    if not row:
        raise HTTPException(404, f"Узел '{node_id}' не найден")
    return dict(row)

@router.delete("/nodes/{node_id}")
def delete_node(node_id: str):
    with db_session() as conn:
        # Удаляем и инцидентные рёбра, чтобы не оставить «висячих» ссылок.
        conn.execute("DELETE FROM edges WHERE from_id=? OR to_id=?", (node_id, node_id))
        conn.execute("DELETE FROM nodes WHERE id=?", (node_id,))
        conn.commit()
    return {"ok": True, "deleted": node_id}

# ── CRUD рёбер графа ─────────────────────────────────────────

@router.get("/edges/", response_model=list[EdgeOut])
def get_edges():
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM edges").fetchall()
    return [dict(r) for r in rows]

@router.post("/edges/", response_model=EdgeOut)
def create_edge(data: EdgeCreate):
    with db_session() as conn:
        nodes = {
            r["id"]: r for r in conn.execute(
                "SELECT * FROM nodes WHERE id IN (?,?)", (data.from_id, data.to_id)
            ).fetchall()
        }
        if data.from_id not in nodes or data.to_id not in nodes:
            raise HTTPException(404, "Один из узлов ребра не найден")
        weight = data.weight
        if weight is None:  # вес по евклидову расстоянию между узлами
            a, b = nodes[data.from_id], nodes[data.to_id]
            weight = round(math.hypot(a["x"] - b["x"], a["y"] - b["y"]), 2)
        cur = conn.execute(
            "INSERT INTO edges (from_id, to_id, weight) VALUES (?,?,?)",
            (data.from_id, data.to_id, weight),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM edges WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)

@router.delete("/edges/{edge_id}")
def delete_edge(edge_id: int):
    with db_session() as conn:
        conn.execute("DELETE FROM edges WHERE id=?", (edge_id,))
        conn.commit()
    return {"ok": True, "deleted": edge_id}

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