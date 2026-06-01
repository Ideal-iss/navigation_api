import math
import networkx as nx
from typing import List, Tuple


def build_graph(nodes, edges) -> nx.Graph:
    """
    Построить граф навигации.

    Узлы добавляются с координатами и этажом. Рёбра добавляются ТОЛЬКО если оба
    их конца присутствуют среди узлов — иначе networkx молча создал бы
    «фантомные» узлы без координат (старый баг: рёбра брались независимо от этажа,
    из-за чего в граф попадали узлы соседних этажей без координат).
    """
    G = nx.Graph()
    for n in nodes:
        keys = n.keys()
        G.add_node(
            n["id"], x=n["x"], y=n["y"], name=n["name"],
            floor=n["floor"] if "floor" in keys else None,
        )
    for e in edges:
        if e["from_id"] in G and e["to_id"] in G:
            G.add_edge(e["from_id"], e["to_id"], weight=e["weight"])
    return G


def _heuristic(G):
    """Эвристика A* — евклидово расстояние между узлами по их координатам."""
    def h(u, v):
        a, b = G.nodes[u], G.nodes[v]
        return math.hypot(a["x"] - b["x"], a["y"] - b["y"])
    return h


def find_route(G: nx.Graph, start: str, end: str) -> Tuple[List[str], float]:
    if start not in G:
        raise ValueError(f"Узел '{start}' не найден в графе")
    if end not in G:
        raise ValueError(f"Узел '{end}' не найден в графе")

    h = _heuristic(G)
    path = nx.astar_path(G, start, end, heuristic=h, weight="weight")
    dist = nx.astar_path_length(G, start, end, heuristic=h, weight="weight")
    return path, dist
