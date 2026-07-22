"""
Pure transform from ONOS REST data into a TopologySnapshot.

No HTTP here, so it can be unit-tested directly against captured ONOS JSON.

ONOS facts this relies on:
  * device ids look like "of:0000000000000001"
  * /onos/v1/links returns DIRECTIONAL links (one entry per direction), each
    with src.device / dst.device and a "state" of ACTIVE | INACTIVE.
We map device ids -> KMS cities and collapse the directional links into
undirected edges.
"""
from __future__ import annotations

from shared.models import TopologyLink, TopologyNode, TopologySnapshot


def build_snapshot_from_onos(
    devices: list[dict],
    links: list[dict],
    mapping: dict[str, dict],
) -> TopologySnapshot:
    """mapping: {device_id: {"id": city_id, "label": city_label}}."""
    nodes: list[TopologyNode] = []
    for dev in devices:
        dev_id = dev.get("id")
        city = mapping.get(dev_id)
        if not city:
            continue  # ignore devices we haven't mapped to a KMS city
        nodes.append(TopologyNode(
            id=city["id"],
            label=city["label"],
            available=bool(dev.get("available", True)),
        ))

    seen: set[tuple[str, str]] = set()
    edges: list[TopologyLink] = []
    for link in links:
        src = (link.get("src") or {}).get("device")
        dst = (link.get("dst") or {}).get("device")
        if src not in mapping or dst not in mapping:
            continue
        a, b = mapping[src]["id"], mapping[dst]["id"]
        if a == b:
            continue
        key = tuple(sorted((a, b)))
        if key in seen:
            continue  # collapse the reverse-direction twin
        seen.add(key)
        status = "up" if link.get("state", "ACTIVE") == "ACTIVE" else "down"
        edges.append(TopologyLink(source=a, target=b, cost=1.0,
                                  type="physical", status=status))

    return TopologySnapshot(nodes=nodes, links=edges)
