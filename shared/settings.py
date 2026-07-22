"""
Centralised configuration. Every value can be overridden via environment
variables (see .env.example). Defaults match the Docker Compose network so
the stack works out-of-the-box with `docker compose up`.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Identity of the running service (set per-container in docker-compose)
    service_name: str = "unknown-service"

    # Downstream service URLs (internal chain) -----------------------------
    identity_url: str = "http://identity-auth:8081"
    topology_url: str = "http://topology-manager:8082"
    pce_url: str = "http://path-computation-engine:8083"
    kom_url: str = "http://key-orchestration-manager:8084"
    provisioning_url: str = "http://service-provisioning:8085"
    audit_url: str = "http://audit-log:8086"

    # Config file paths ----------------------------------------------------
    topology_config: str = "/app/config/topology.yaml"
    kms_registry: str = "/app/config/kms_registry.yaml"
    domains_config: str = "/app/config/domains.yaml"

    # Topology source ------------------------------------------------------
    # "static" -> read topology_config (YAML); good for tests / no-docker dev.
    # "onos"   -> discover the topology from ONOS (the SDN controller).
    topology_source: str = "static"
    onos_base_url: str = "http://onos:8181"
    onos_user: str = "onos"
    onos_password: str = "rocks"
    onos_mapping: str = "/app/config/onos_mapping.yaml"

    # Audit store ----------------------------------------------------------
    audit_db_path: str = "/app/data/audit.db"

    # HTTP behaviour -------------------------------------------------------
    http_timeout: float = 10.0
    audit_timeout: float = 3.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
