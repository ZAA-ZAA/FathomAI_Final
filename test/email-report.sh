#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

require_api_key
JOB_ID="${1:-}"
TARGET="${2:-summary}"
RECIPIENT_EMAIL="${3:-zoenaldueza@gmail.com}"
ensure_arg "${JOB_ID}" "Usage: ./email-report.sh <job_id> [summary|transcript] [recipient_email]"
ensure_arg "${RECIPIENT_EMAIL}" "Recipient email is required"

curl -X POST "${API_BASE_URL}/videos/${JOB_ID}/reports/${TARGET}/email" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{
    "recipient_email": "'"${RECIPIENT_EMAIL}"'",
    "show_timestamps": true
  }'
echo
