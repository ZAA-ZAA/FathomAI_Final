#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

require_api_key
JOB_ID="${1:-}"
TARGET="${2:-summary}"
OUTPUT_PATH="${3:-}"
ensure_arg "${JOB_ID}" "Usage: ./download-report.sh <job_id> [summary|transcript] [output_path]"

if [[ -z "${OUTPUT_PATH}" ]]; then
  if [[ "${TARGET}" == "transcript" ]]; then
    OUTPUT_PATH="./transcript-report.pdf"
  else
    OUTPUT_PATH="./summary-report.pdf"
  fi
fi

curl -L "${API_BASE_URL}/videos/${JOB_ID}/reports/${TARGET}" \
  -H "X-API-Key: ${API_KEY}" \
  -o "${OUTPUT_PATH}"

echo "Saved ${TARGET} report to ${OUTPUT_PATH}"
