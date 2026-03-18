#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

require_api_key
JOB_ID="${1:-}"
OUTPUT_PATH="${2:-./video-source.mp4}"
ensure_arg "${JOB_ID}" "Usage: ./download-source.sh <job_id> [output_path]"

curl -L "${API_BASE_URL}/videos/${JOB_ID}/source" \
  -H "X-API-Key: ${API_KEY}" \
  -o "${OUTPUT_PATH}"

echo "Saved source video to ${OUTPUT_PATH}"
