#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

require_api_key

curl -X POST "${API_BASE_URL}/videos/upload" \
  -H "X-API-Key: ${API_KEY}" \
  -F "file_path=/mnt/c/Users/zoen/Downloads/videos_40262bb1-ccf3-416f-a3ca-9ec4598fa101_7f333498-8fe3-457a-a420-3afa4f348102_google-drive-import.mp4" \
  -F "language_hint=auto" \
  -F "notify_email=zoenaldueza@gmail.com" \
  -F "export_pdf=true" \
  -F "export_pdf_path=/mnt/c/Users/zoen/Downloads/summary-report2.pdf"
echo
