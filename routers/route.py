import math
import networkx as nx
from fastapi import APIRouter, HTTPException
from database import db_session
from models import (
    RouteRequest, RoutePointRequest, RouteOut,
    NodeOut, NodeCreate, NodeUpdate, EdgeCreate, EdgeOut,
)
from pathfinding import build_graph, find_route

VIRTUAL_LINKS = 3
VIRTUAL_ID = "__start__"

router = APIRouter(prefix="/route", tags=["route"])

# Node name comes from room; fallback to stored name; empty if neither set
_NODE_SELECT = """
    SELECT n.id,
           COALESCE(r.name, NULLIF(n.name, ''), '') AS name,
           n.x, n.y,
           n.floor_id AS floor,
           n.room_id
    FROM nodes n
    LEFT JOIN rooms r ON r.id = n.room_id
"""


@router.get("/diagnostics/")
def graph_diagnostics(floor: int = 1):
    with db_session() as conn:
        nodes = [dict(r) for r in conn.execute(
            _NODE_SELECT + " WHERE n.floor_id=?", (floor,)).fetchall()]
        edges = [dict(r) for r in conn.execute("SELECT * FROM edges").fetchall()]

    G = build_graph(nodes, edges)
    isolated = sorted(n for n in G.nodes if G.degree(n) == 0)
    components = sorted(
        (sorted(c) for c in nx.connected_components(G)), key=len, reverse=True
    )
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
        rows = conn.execute(_NODE_SELECT + " WHERE n.floor_id=?", (floor,)).fetchall()
    return [dict(r) for r in rows]


@router.post("/nodes/", response_model=NodeOut)
def create_node(data: NodeCreate):
    with db_session() as conn:
        exists = conn.execute("SELECT 1 FROM nodes WHERE id=?", (data.id,)).fetchone()
        if exists:
            raise HTTPException(409, f"Узел '{data.id}' уже существует")
        conn.execute(
            "INSERT INTO nodes (id, name, x, y, floor_id, room_id) VALUES (?,?,?,?,?,?)",
            (data.id, data.name, data.x, data.y, data.floor, data.room_id),
        )
        conn.commit()
        row = conn.execute(_NODE_SELECT + " WHERE n.id=?", (data.id,)).fetchone()
    return dict(row)


@router.patch("/nodes/{node_id}", response_model=NodeOut)
def update_node(node_id: str, data: NodeUpdate):
    raw = data.model_dump(exclude_unset=True)
    if not raw:
        raise HTTPException(400, "Нет данных для обновления")
    db_fields = {("floor_id" if k == "floor" else k): v for k, v in raw.items()}
    sets = ", ".join(f"{k}=?" for k in db_fields)
    with db_session() as conn:
        conn.execute(
            f"UPDATE nodes SET {sets} WHERE id=?",
            (*db_fields.values(), node_id),
        )
        conn.commit()
        row = conn.execute(_NODE_SELECT + " WHERE n.id=?", (node_id,)).fetchone()
    if not row:
        raise HTTPException(404, f"Узел '{node_id}' не найден")
    return dict(row)


@router.delete("/nodes/{node_id}")
def delete_node(node_id: str):
    with db_session() as conn:
        conn.execute("DELETE FROM edges WHERE from_id=? OR to_id=?", (node_id, node_id))
        conn.execute("DELETE FROM nodes WHERE id=?", (node_id,))
        conn.commit()
    return {"ok": True, "deleted": node_id}


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
                _NODE_SELECT + " WHERE n.id IN (?,?)", (data.from_id, data.to_id)
            ).fetchall()
        }
        if data.from_id not in nodes or data.to_id not in nodes:
            raise HTTPException(404, "Один из узлов ребра не найден")
        weight = data.weight
        if weight is None:
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
    with db_session() as conn:
        all_nodes = conn.execute(_NODE_SELECT).fetchall()
        floor_nodes = conn.execute(
            _NODE_SELECT + " WHERE n.floor_id=?", (req.floor,)
        ).fetchall()
        edges = conn.execute("SELECT * FROM edges").fetchall()

    if not floor_nodes:
        raise HTTPException(404, "Граф для этого этажа не найден")

    G = build_graph(all_nodes, edges)
    try:
        path, dist = find_route(G, req.from_node, req.to_node)
    except Exception as e:
        raise HTTPException(400, str(e))

    return RouteOut(nodes=path, total_distance=round(dist, 2))


@router.post("/from-point/", response_model=RouteOut)
def get_route_from_point(req: RoutePointRequest):
    with db_session() as conn:
        all_nodes = conn.execute(_NODE_SELECT).fetchall()
        edges = conn.execute("SELECT * FROM edges").fetchall()

    G = build_graph(all_nodes, edges)
    floor_ids = [n["id"] for n in all_nodes if n["floor"] == req.floor and n["id"] in G]
    if not floor_ids:
        raise HTTPException(404, "Граф для этого этажа не найден")
    if req.to_node not in G:
        raise HTTPException(400, f"Узел '{req.to_node}' не найден в графе")

    def dist_to(nid: str) -> float:
        a = G.nodes[nid]
        return math.hypot(a["x"] - req.x, a["y"] - req.y)

    nearest = sorted(floor_ids, key=dist_to)[:VIRTUAL_LINKS]
    G.add_node(VIRTUAL_ID, x=req.x, y=req.y, name="start", floor=req.floor)
    for nid in nearest:
        G.add_edge(VIRTUAL_ID, nid, weight=round(dist_to(nid), 2))

    try:
        path, dist = find_route(G, VIRTUAL_ID, req.to_node)
    except Exception as e:
        raise HTTPException(400, str(e))

    real_path = [p for p in path if p != VIRTUAL_ID]
    return RouteOut(
        nodes=real_path,
        total_distance=round(dist, 2),
        start_x=req.x,
        start_y=req.y,
    )
