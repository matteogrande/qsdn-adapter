"""Unit test for the ONOS -> TopologySnapshot transform (no live ONOS needed)."""
import yaml

from services.path_computation_engine.app.path_engine import compute_path
from services.topology_manager.app.onos_source import build_snapshot_from_onos
from tests.conftest import ROOT

ONOS_MAPPING = ROOT / "config" / "onos_mapping.yaml"

# s1=milano s2=torino s3=genova s4=venezia s5=bologna s6=parma s7=la_spezia
# s8=padova s9=pavia s10=ferrara s11=verona
MESH = [
    (1, 2), (2, 3), (3, 7), (7, 6), (1, 6), (6, 5), (6, 8), (8, 4),
    # Pavia relay (west redundancy)
    (1, 9), (9, 3), (9, 6),
    # Ferrara relay (east redundancy)
    (5, 10), (10, 8), (10, 4),
    # Verona main KMS (north-east mesh)
    (11, 8), (11, 10), (11, 4),
]


def _mapping():
    return yaml.safe_load(ONOS_MAPPING.read_text(encoding="utf-8"))["devices"]


def _dpid(n: int) -> str:
    # DPIDs are hex, so switch 10/11 map to ...0a / ...0b (see onos_mapping.yaml).
    return f"of:00000000000000{n:02x}"


def _devices():
    return [{"id": _dpid(n), "type": "SWITCH", "available": True} for n in range(1, 12)]


def _links(down_pair=None):
    out = []
    for a, b in MESH:
        state = "INACTIVE" if down_pair == {a, b} else "ACTIVE"
        out.append({"src": {"device": _dpid(a), "port": "2"},
                    "dst": {"device": _dpid(b), "port": "1"},
                    "type": "DIRECT", "state": state})
        out.append({"src": {"device": _dpid(b), "port": "1"},
                    "dst": {"device": _dpid(a), "port": "2"},
                    "type": "DIRECT", "state": state})
    return out


def test_onos_builds_the_mesh():
    snap = build_snapshot_from_onos(_devices(), _links(), _mapping())
    assert {n.id for n in snap.nodes} == {"milano", "torino", "genova", "venezia",
                                          "bologna", "parma", "la_spezia", "padova",
                                          "pavia", "ferrara", "verona"}
    assert len(snap.links) == 17         # directional twins collapsed to 17 undirected edges
    path = compute_path(snap, "milano", "venezia")
    assert path.path_nodes == ["milano", "parma", "padova", "venezia"]


def test_onos_inactive_link_becomes_down():
    # s1=milano, s6=parma -> mark the Milano-Parma relay link INACTIVE
    snap = build_snapshot_from_onos(_devices(), _links(down_pair={1, 6}), _mapping())
    down = [l for l in snap.links if {l.source, l.target} == {"milano", "parma"}]
    assert down and down[0].status == "down"
    path = compute_path(snap, "milano", "venezia")
    # With Milano-Parma down the Pavia relay gives a 4-hop backup.
    assert path.path_nodes == ["milano", "pavia", "parma", "padova", "venezia"]
