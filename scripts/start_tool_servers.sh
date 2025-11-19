#!/usr/bin/env bash
set -euo pipefail

# Launch all MCP tool servers (search/fetch, company lookup, patents, financial metrics)
# Press Ctrl+C to stop them all together.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"

HOST="${MCP_TOOL_HOST:-127.0.0.1}"

declare -a PIDS=()

cleanup() {
  if ((${#PIDS[@]} > 0)); then
    for pid in "${PIDS[@]}"; do
      if kill -0 "$pid" >/dev/null 2>&1; then
        kill "$pid" >/dev/null 2>&1 || true
      fi
    done
  fi
}

trap cleanup EXIT INT TERM

start_server() {
  local module="$1"
  local port="$2"
  echo "Starting ${module} on ${HOST}:${port}"
  python3 -m uvicorn "${module}" --host "${HOST}" --port "${port}" --log-level info &
  PIDS+=("$!")
}

start_server "servers.search_service:app" 7001
start_server "servers.crunchbase_service:app" 7002
start_server "servers.patents_service:app" 7003
start_server "servers.financials_service:app" 7004
start_server "servers.esg_service:app" 7005
start_server "servers.academic_search_service:app" 7006
start_server "servers.sustainability_service:app" 7007

echo "All 7 MCP services are running. Press Ctrl+C to stop."
wait "${PIDS[@]}"
