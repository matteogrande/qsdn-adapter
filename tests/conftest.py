"""Test bootstrap: make repo importable and point config at the repo files."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Point shared.settings at the in-repo config (defaults target /app/... in docker)
os.environ.setdefault("TOPOLOGY_CONFIG", str(ROOT / "config" / "topology.yaml"))
os.environ.setdefault("KMS_REGISTRY", str(ROOT / "config" / "kms_registry.yaml"))

TOPOLOGY_PATH = ROOT / "config" / "topology.yaml"
KMS_REGISTRY_PATH = ROOT / "config" / "kms_registry.yaml"
