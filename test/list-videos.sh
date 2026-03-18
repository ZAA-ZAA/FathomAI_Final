#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

require_api_key

curl -X GET "${API_BASE_URL}/videos" \
  -H "X-API-Key: ${API_KEY}"
echo
