#!/usr/bin/env bash
# Simulates the ONOS REST client sending a virtual-circuit request to the
# adapter's Northbound API Gateway, then prints the audit trail.
set -euo pipefail
GATEWAY="${GATEWAY:-http://localhost:8080}"
AUDIT="${AUDIT:-http://localhost:8086}"
REQ_ID="req-demo-001"

echo "==> POST ${GATEWAY}/adapter/v1/virtual-circuits"
curl -s -X POST "${GATEWAY}/adapter/v1/virtual-circuits" \
  -H "Content-Type: application/json" \
  -d "{
    \"request_id\": \"${REQ_ID}\",
    \"source\": \"Monza\",
    \"destination\": \"Venezia\",
    \"service_type\": \"qkd_virtual_circuit\",
    \"key_size\": 256,
    \"num_keys\": 1,
    \"priority\": \"normal\"
  }" | python3 -m json.tool

echo ""
echo "==> Audit trail for ${REQ_ID}"
curl -s "${AUDIT}/audit/v1/events?request_id=${REQ_ID}" | python3 -m json.tool
