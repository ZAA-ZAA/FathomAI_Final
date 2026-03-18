#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

require_api_key
JOB_ID="${1:-}"
ensure_arg "${JOB_ID}" "Usage: ./retry-job.sh <job_id>"

curl -X POST "${API_BASE_URL}/videos/${JOB_ID}/retry" \
  -H "X-API-Key: ${API_KEY}"
echo
