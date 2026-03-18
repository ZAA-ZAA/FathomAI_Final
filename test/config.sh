#!/usr/bin/env bash
set -euo pipefail

# change the line 6 to your API key before running the tests
API_BASE_URL="${API_BASE_URL:-http://localhost:8000/api}"
API_KEY="${API_KEY:-pthm_6vRMYPlH66bW914S9rG9x9ZMjtYl_nXkj-UnkhDQDuA}"

require_api_key() {
  if [[ -z "${API_KEY}" || "${API_KEY}" == "pthm_change_me" ]]; then
    echo "Set API_KEY in test/config.sh before running this script." >&2
    exit 1
  fi
}

ensure_arg() {
  local value="${1:-}"
  local message="${2:-Missing required argument}"
  if [[ -z "$value" ]]; then
    echo "$message" >&2
    exit 1
  fi
}
