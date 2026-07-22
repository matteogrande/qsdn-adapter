"""
Endpoint resolver: maps logical endpoints requested by ONOS (e.g. cities
without a local KMS) onto a KMS domain/node in the topology.

Example: "Monza" has no KMS -> resolved onto the Milano KMS domain.
"""
from __future__ import annotations

# Aliases for cities that do not host their own KMS.
ALIASES: dict[str, str] = {
    "monza": "milano",
    "milano": "milano",
    "como": "milano",
    "torino": "torino",
    "genova": "genova",
    "venezia": "venezia",
    "mestre": "venezia",
    "bologna": "bologna",
    # Trusted relay nodes (own KMS, added for QKD distance constraints).
    "parma": "parma",
    "la spezia": "la_spezia",
    "laspezia": "la_spezia",
    "padova": "padova",
    "firenze": "firenze",
    "roma": "roma",
    "latina": "roma",
    "napoli": "napoli",
    # Densification: Pavia/Ferrara relays + Verona main KMS.
    "pavia": "pavia",
    "ferrara": "ferrara",
    "verona": "verona",
    "vicenza": "verona",
}


class ResolutionError(ValueError):
    pass


def _normalise(name: str) -> str:
    return name.strip().lower().replace(" kms", "")


def resolve_endpoint(name: str, node_labels: dict[str, str]) -> tuple[str, str]:
    """Return (node_id, label) for a logical endpoint name.

    node_labels maps node_id -> label, used to attach the canonical KMS label.
    """
    key = _normalise(name)
    node_id = ALIASES.get(key, key)
    if node_id not in node_labels:
        raise ResolutionError(
            f"Cannot resolve endpoint '{name}' to a known KMS domain"
        )
    return node_id, node_labels[node_id]
