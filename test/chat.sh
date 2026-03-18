#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

require_api_key
JOB_ID="${1:-}"
QUESTION="${2:-What decisions were made in this video?}"
ensure_arg "${JOB_ID}" "Usage: ./chat.sh <job_id> [question]"

curl -X POST "${API_BASE_URL}/videos/${JOB_ID}/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{
    "question": "'"${QUESTION}"'",
    "chat_history": []
  }'
echo
