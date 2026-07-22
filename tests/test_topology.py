from collections import Counter

from shared.topology_loader import load_topology
from tests.conftest import TOPOLOGY_PATH

ALL_CITIES = {"milano", "torino", "genova", "venezia", "bologna",
              "parma", "la_spezia", "padova", "pavia", "ferrara", "verona"}


def test_loads_mesh_nodes():
    snap = load_topology(TOPOLOGY_PATH)
    ids = {n.id for n in snap.nodes}
    assert ids == ALL_CITIES
    assert any(n.label == "Milano KMS" for n in snap.nodes)


def test_relay_nodes_present():
    snap = load_topology(TOPOLOGY_PATH)
    labels = {n.id: n.label for n in snap.nodes}
    # Original trusted relays + the densification relays Pavia/Ferrara.
    assert labels["parma"] == "Parma KMS"
    assert labels["la_spezia"] == "La Spezia KMS"
    assert labels["padova"] == "Padova KMS"
    assert labels["pavia"] == "Pavia KMS"
    assert labels["ferrara"] == "Ferrara KMS"
    # Verona is an extra MAIN KMS site.
    assert labels["verona"] == "Verona KMS"


def test_densified_mesh_is_physical_with_redundant_corridors():
    snap = load_topology(TOPOLOGY_PATH)
    assert all(link.type == "physical" for link in snap.links)
    assert len(snap.links) == 17           # 8 original + 9 densification edges
    degree = Counter()
    for link in snap.links:
        degree[link.source] += 1
        degree[link.target] += 1
    # Parma stays the western hub; Ferrara/Padova become eastern hubs, giving
    # the PCE two independent corridors towards Venezia instead of one.
    assert degree["parma"] == 5
    assert degree["ferrara"] == 4
    assert degree["padova"] == 4
    assert degree["venezia"] == 3          # padova + ferrara + verona
    assert degree["bologna"] == 2          # parma + ferrara (no longer a leaf)
    assert degree["verona"] == 3
    assert sum(degree.values()) == 2 * len(snap.links)
