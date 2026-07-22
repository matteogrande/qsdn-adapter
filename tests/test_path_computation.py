from services.identity_auth.app.resolver import resolve_endpoint
from services.path_computation_engine.app.path_engine import compute_path
from shared.topology_loader import load_topology
from tests.conftest import TOPOLOGY_PATH


def _snapshot():
    return load_topology(TOPOLOGY_PATH)


def test_monza_resolves_to_milano():
    labels = {n.id: n.label for n in _snapshot().nodes}
    node_id, label = resolve_endpoint("Monza", labels)
    assert node_id == "milano" and label == "Milano KMS"


def test_la_spezia_resolves_to_its_own_kms():
    labels = {n.id: n.label for n in _snapshot().nodes}
    node_id, label = resolve_endpoint("La Spezia", labels)
    assert node_id == "la_spezia" and label == "La Spezia KMS"


def test_short_path_goes_via_parma_and_padova():
    # mesh: Milano->Parma->Padova->Venezia (3 hops) beats the long way round
    # the ring Milano->Torino->Genova->La Spezia->Parma->Padova->Venezia (6).
    path = compute_path(_snapshot(), "milano", "venezia")
    assert path.path_nodes == ["milano", "parma", "padova", "venezia"]
    assert path.hops == 3 and path.total_cost == 3.0


def test_fallback_when_milano_parma_down():
    # with the direct Milano-Parma relay link down, the Pavia relay now offers
    # a short backup (Milano->Pavia->Parma) instead of the whole west ring, so
    # the fallback drops from 6 hops to 4 — that's the point of densifying.
    snap = _snapshot()
    for link in snap.links:
        if {link.source, link.target} == {"milano", "parma"}:
            link.status = "down"
    path = compute_path(snap, "milano", "venezia")
    assert path.path_nodes == ["milano", "pavia", "parma", "padova", "venezia"]
    assert path.hops == 4


def test_short_path_to_verona_via_padova():
    # Verona (new main KMS) hangs off the north-east mesh: the cheapest way in
    # from Milano is Milano->Parma->Padova->Verona (3 hops).
    path = compute_path(_snapshot(), "milano", "verona")
    assert path.path_nodes == ["milano", "parma", "padova", "verona"]
    assert path.hops == 3 and path.total_cost == 3.0


def test_bologna_shortest_still_through_parma():
    # Bologna now also reaches the mesh via Ferrara, but the cheapest path from
    # Milano stays the direct Milano->Parma->Bologna hop.
    snap = _snapshot()
    path = compute_path(snap, "milano", "bologna")
    assert path.path_nodes == ["milano", "parma", "bologna"]
    assert path.hops == 2
