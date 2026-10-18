#!/usr/bin/env bash
# Start the Hugo preview server and the local post admin together.
# Stop both with Ctrl+C.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Starting Hugo preview on http://localhost:1313"
hugo server --buildDrafts --baseURL "http://localhost:1313/" --appendPort=false &
HUGO_PID=$!

echo "Starting post admin on http://localhost:1314"
python3 admin/admin.py &
ADMIN_PID=$!

trap 'kill "$HUGO_PID" "$ADMIN_PID" 2>/dev/null || true' EXIT INT TERM

echo
echo "  Site  : http://localhost:1313"
echo "  Admin : http://localhost:1314"
echo "  Ctrl+C to stop both."
echo
wait
