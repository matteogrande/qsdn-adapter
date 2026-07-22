"""
YAML topology loader. Pure helper (no FastAPI), so it can be unit-tested
directly and reused by Topology Manager.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from shared.models import TopologyLink, TopologyNode, TopologySnapshot


def load_topology(path: str | Path) -> TopologySnapshot:
    """Load nodes + physical links + virtual links into a TopologySnapshot."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

    nodes = [
        TopologyNode(id=n["id"], label=n["label"], available=n.get("available", True))
        for n in data.get("nodes", [])
    ]

    links: list[TopologyLink] = []
    for raw in data.get("links", []):
        links.append(TopologyLink(**{"type": "physical", **raw}))
    for raw in data.get("virtual_links", []):
        links.append(TopologyLink(**{"type": "vpn", **raw}))

    return TopologySnapshot(nodes=nodes, links=links)
