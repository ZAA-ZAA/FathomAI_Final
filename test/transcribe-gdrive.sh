#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

require_api_key

curl -X POST "${API_BASE_URL}/videos/transcribe" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{
    "video_url": "https://drive.google.com/file/d/1pfOyxA8Nsqkrjki3ijODeveUALlXdEJn/view?usp=sharing",
    "language_hint": "auto",
    "notify_email": "zoenaldueza@gmail.com",
    "export_pdf": true,
    "export_pdf_path": "/mnt/c/Users/zoen/Downloads/summary-report3.pdf"
  }'
echo
