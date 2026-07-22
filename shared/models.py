"""
Pydantic models shared by all microservices.

The core idea: a single AdapterContext object travels along the internal
microservice chain. Each service fills in its own slice of the context and
forwards it to the next hop. The final response that goes back to ONOS is
built by Service Provisioning from the fully-populated context.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Public contract (ONOS <-> Northbound API Gateway)
# --------------------------------------------------------------------------- #
class VirtualCircuitRequest(BaseModel):
    """Request sent by the ONOS REST client to the adapter."""
    request_id: str
    source: str
    destination: str
    service_type: str = "qkd_virtual_circuit"
    key_size: int = 256
    num_keys: int = 1
    priority: str = "normal"


class KeyInfo(BaseModel):
    key_id: str
    size: int
    status: str = "available"


class VirtualCircuitResponse(BaseModel):
    """Final response returned to ONOS through the Northbound API Gateway."""
    request_id: str
    status: Literal["PROVISIONED", "REJECTED", "ERROR"] = "PROVISIONED"
    source: str
    destination: str
    resolved_source_domain: Optional[str] = None
    resolved_destination_domain: Optional[str] = None
    selected_path: list[str] = Field(default_factory=list)
    kms_chain: list[str] = Field(default_factory=list)
    keys: list[KeyInfo] = Field(default_factory=list)
    message: str = ""


# --------------------------------------------------------------------------- #
# Topology view (produced by Topology Manager, consumed by PCE)
# --------------------------------------------------------------------------- #
class TopologyNode(BaseModel):
    id: str
    label: str
    available: bool = True


class TopologyLink(BaseModel):
    source: str
    target: str
    cost: float = 1.0
    type: Literal["physical", "vpn"] = "physical"
    status: Literal["up", "down"] = "up"


class TopologySnapshot(BaseModel):
    nodes: list[TopologyNode] = Field(default_factory=list)
    links: list[TopologyLink] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Resolution / path / keys (intermediate context slices)
# --------------------------------------------------------------------------- #
class ResolvedEndpoints(BaseModel):
    source_node: str
    source_domain: str
    destination_node: str
    destination_domain: str


class ComputedPath(BaseModel):
    path_nodes: list[str] = Field(default_factory=list)     # node ids, e.g. ["milano", ...]
    path_domains: list[str] = Field(default_factory=list)   # labels, e.g. ["Milano KMS", ...]
    total_cost: float = 0.0
    hops: int = 0


class KeyOrchestrationResult(BaseModel):
    kms_chain: list[str] = Field(default_factory=list)      # labels of KMS queried
    keys: list[KeyInfo] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# AdapterContext: the payload that flows through the internal chain
# --------------------------------------------------------------------------- #
class AdapterContext(BaseModel):
    request: VirtualCircuitRequest
    status: Literal["NEW", "AUTHORIZED", "RESOLVED", "ROUTED", "KEYED",
                    "PROVISIONED", "REJECTED", "ERROR"] = "NEW"
    error: Optional[str] = None

    resolved: Optional[ResolvedEndpoints] = None
    topology: Optional[TopologySnapshot] = None
    path: Optional[ComputedPath] = None
    keys: Optional[KeyOrchestrationResult] = None
    response: Optional[VirtualCircuitResponse] = None


# --------------------------------------------------------------------------- #
# Audit log
# --------------------------------------------------------------------------- #
class AuditEvent(BaseModel):
    request_id: str
    service: str
    event_type: str
    timestamp: str = Field(default_factory=_now)
    endpoints: Optional[dict[str, Any]] = None
    topology: Optional[Any] = None
    selected_path: Optional[list[str]] = None
    kms_called: Optional[list[str]] = None
    keys: Optional[list[str]] = None
    backend: Optional[dict[str, str]] = None
    key_shared_verified: Optional[bool] = None
    error: Optional[str] = None
    detail: Optional[dict[str, Any]] = None
