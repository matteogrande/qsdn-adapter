"""
Topology Manager logic: builds the network snapshot from the configured
source, caches it, and (in static/demo mode) supports LIVE runtime edits so
the dashboard can add/remove nodes and links or toggle link state without
touching files or restarting.

  TOPOLOGY_SOURCE=static  -> load_topology(topology_config)   [YAML mesh]
  TOPOLOGY_SOURCE=onos    -> discover devices+links from ONOS, map to cities

Live edits mutate the cached snapshot in memory. POST /topology/v1/refresh
reloads from the source and discards the live edits (a clean "reset").
"""
from __future__ import annotations

from pathlib import Path

import yaml

from shared.models import TopologyLink, TopologyNode, TopologySnapshot
from shared.settings import get_settings
from shared.topology_loader import load_topology
from .onos_source import build_snapshot_from_onos

_cache: dict[str, TopologySnapshot | None] = {"snapshot": None}


def _load_mapping(path: str) -> dict[str, dict]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return data.get("devices", {})


async def _from_onos() -> TopologySnapshot:
    from .onos_client import fetch_devices_and_links  # local import: optional dep
    settings = get_settings()
    devices, links = await fetch_devices_and_links()
    mapping = _load_mapping(settings.onos_mapping)
    return build_snapshot_from_onos(devices, links, mapping)


async def get_snapshot() -> TopologySnapshot:
    if _cache["snapshot"] is not None:
        return _cache["snapshot"]
    settings = get_settings()
    if settings.topology_source == "onos":
        snapshot = await _from_onos()
    else:
        snapshot = load_topology(settings.topology_config)
    _cache["snapshot"] = snapshot
    return snapshot


async def refresh() -> TopologySnapshot:
    """Reset: reload from source (discards live edits)."""
    _cache["snapshot"] = None
    return await get_snapshot()


# --------------------------------------------------------------------------- #
# Live runtime edits (used by the dashboard). Mutate the cached snapshot.
# --------------------------------------------------------------------------- #
def _same(a: str, b: str, c: str, d: str) -> bool:
    return {a, b} == {c, d}


async def upsert_node(node_id: str, label: str | None = None,
                      available: bool = True) -> TopologySnapshot:
    snap = await get_snapshot()
    for n in snap.nodes:
        if n.id == node_id:
            if label is not None:
                n.label = label
            n.available = available
            return snap
    snap.nodes.append(TopologyNode(id=node_id, label=label or node_id,
                                   available=available))
    return snap


async def remove_node(node_id: str) -> TopologySnapshot:
    snap = await get_snapshot()
    snap.nodes = [n for n in snap.nodes if n.id != node_id]
    snap.links = [l for l in snap.links
                  if l.source != node_id and l.target != node_id]
    return snap


async def upsert_link(source: str, target: str, cost: float = 1.0,
                      link_type: str = "physical",
                      status: str = "up") -> TopologySnapshot:
    snap = await get_snapshot()
    for l in snap.links:
        if _same(l.source, l.target, source, target):
            l.cost, l.type, l.status = cost, link_type, status
            return snap
    snap.links.append(TopologyLink(source=source, target=target, cost=cost,
                                   type=link_type, status=status))
    return snap


async def remove_link(source: str, target: str) -> TopologySnapshot:
    snap = await get_snapshot()
    snap.links = [l for l in snap.links
                  if not _same(l.source, l.target, source, target)]
    return snap


async def set_link_status(source: str, target: str,
                          status: str) -> TopologySnapshot:
    snap = await get_snapshot()
    for l in snap.links:
        if _same(l.source, l.target, source, target):
            l.status = status
    return snap
