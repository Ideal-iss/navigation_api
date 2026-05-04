import networkx as nx
from typing import List, Tuple

def build_graph(nodes, edges) -> nx.Graph:
    G = nx.Graph()
    for n in nodes:
        G.add_node(n["id"], x=n["x"], y=n["y"], name=n["name"])
    for e in edges:
        G.add_edge(e["from_id"], e["to_id"], weight=e["weight"])
    return G

def find_route(G: nx.Graph, start: str, end: str) -> Tuple[List[str], float]:
    if start not in G:
        raise ValueError(f"Узел '{start}' не найден в графе")
    if end not in G:
        raise ValueError(f"Узел '{end}' не найден в графе")

    path = nx.astar_path(G, start, end, weight="weight")
    dist = nx.astar_path_length(G, start, end, weight="weight")
    return path, dist