#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

require_api_key
JOB_ID="${1:-}"
INSTRUCTION="${2:-Focus on key decisions, risks, and next steps.}"
ensure_arg "${JOB_ID}" "Usage: ./regenerate-summary.sh <job_id> [instruction]"

curl -X POST "${API_BASE_URL}/videos/${JOB_ID}/summary/regenerate" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{
    "instruction": "'"${INSTRUCTION}"'"
  }'
echo
