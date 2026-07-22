"""
Path computation logic. Pure function over a TopologySnapshot so it can be
unit-tested without running any service.

Rules:
  * only links with status == "up" are usable
  * only nodes with available == True are usable
  * weight = link cost; shortest path by total cost (Dijkstra via networkx)
"""
from __future__ import annotations

import networkx as nx

from shared.models import ComputedPath, TopologySnapshot


class NoPathError(Exception):
    pass


def build_graph(snapshot: TopologySnapshot) -> nx.Graph:
    g = nx.Graph()
    for node in snapshot.nodes:
        if node.available:
            g.add_node(node.id, label=node.label)
    for link in snapshot.links:
        if link.status != "up":
            continue
        if link.source not in g or link.target not in g:
            continue
        # Keep the cheapest edge if both a physical and a virtual link exist.
        if g.has_edge(link.source, link.target):
            if g[link.source][link.target]["cost"] <= link.cost:
                continue
        g.add_edge(link.source, link.target, cost=link.cost, type=link.type)
    return g


def compute_path(snapshot: TopologySnapshot, source: str, destination: str) -> ComputedPath:
    g = build_graph(snapshot)
    labels = {n.id: n.label for n in snapshot.nodes}

    if source not in g:
        raise NoPathError(f"Source node '{source}' is unavailable")
    if destination not in g:
        raise NoPathError(f"Destination node '{destination}' is unavailable")

    try:
        nodes = nx.shortest_path(g, source, destination, weight="cost")
    except nx.NetworkXNoPath as exc:
        raise NoPathError(f"No path between '{source}' and '{destination}'") from exc

    total = nx.path_weight(g, nodes, weight="cost") if len(nodes) > 1 else 0.0
    return ComputedPath(
        path_nodes=nodes,
        path_domains=[labels.get(n, n) for n in nodes],
        total_cost=float(total),
        hops=max(len(nodes) - 1, 0),
    )
