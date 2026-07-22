#!/usr/bin/env bash
# Activate the ONOS apps needed for OpenFlow switch + link discovery.
# Run once after `docker compose up`, before launching the Mininet ring.
set -euo pipefail
ONOS="${ONOS:-http://localhost:8181}"
AUTH="${ONOS_AUTH:-onos:rocks}"

for app in org.onosproject.openflow org.onosproject.fwd; do
  echo "==> activating ${app}"
  curl -s -u "${AUTH}" -X POST "${ONOS}/onos/v1/applications/${app}/active" >/dev/null
done
echo "Done. Check discovered devices with:"
echo "  curl -u ${AUTH} ${ONOS}/onos/v1/devices | python3 -m json.tool"
