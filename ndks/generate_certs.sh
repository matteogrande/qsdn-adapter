#!/usr/bin/env bash
# Generate CA + KME + SAE certificates for ALL 14 Next Door KMEs (full mesh:
# 9 main KMS sites + 5 trusted relay nodes parma / la_spezia / padova / pavia /
# ferrara; verona is a main KMS).
# CNs MUST equal the UUIDs used in docker-compose.yml and in
# config/kms_registry.ndks.yaml. Run once before:
#   KMS_REGISTRY=/app/config/kms_registry.ndks.yaml docker compose --profile ndks up -d --build
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
mkdir -p certs && cd certs

CITIES=(milano torino genova venezia bologna firenze roma napoli parma la_spezia padova pavia ferrara verona)

echo "==> CA"
openssl genrsa -out ca.key.pem 4096 2>/dev/null
openssl req -x509 -new -nodes -key ca.key.pem -sha256 -days 730 \
  -out ca.crt.pem -subj '/CN=CA/O=QSDN/C=IT' 2>/dev/null

gen() {  # name  CN
  openssl req -new -nodes -newkey rsa:2048 -keyout "$1.key.pem" -out "$1.csr" \
    -subj "/CN=$2/O=$1/C=IT" 2>/dev/null
  openssl x509 -req -in "$1.csr" -CA ca.crt.pem -CAkey ca.key.pem -CAcreateserial \
    -out "$1.crt.pem" -days 365 -sha256 2>/dev/null
  rm -f "$1.csr"
}

n=1
for city in "${CITIES[@]}"; do
  # Zero-padded 12-digit tail so 2-digit indices (10, 11) stay valid UUIDs.
  kme_id=$(printf '10000000-0000-0000-0000-%012d' "$n")
  sae_id=$(printf '5ae00000-0000-0000-0000-%012d' "$n")
  echo "==> ${city}  (KME ${kme_id} / SAE ${sae_id})"
  gen "kme-${city}" "${kme_id}"
  gen "sae-${city}" "${sae_id}"
  n=$((n+1))
done
rm -f ca.srl
echo "Fatto. Certificati per ${#CITIES[@]} città in ndks/certs/"
