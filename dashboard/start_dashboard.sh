#!/bin/bash
# Life OS v2 — Single Dashboard Server
# Replaces start_all_dashboards.sh (7 servers → 1)
# Usage: bash start_dashboard.sh

DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=8077

echo "=========================================="
echo "  Owens Life OS v2 — Dashboard"
echo "=========================================="
echo ""

# Kill any existing dashboard servers on old ports
for port in 8077 8078 8079 8080 8081 8082 8083; do
  pid=$(lsof -ti:$port 2>/dev/null)
  if [ -n "$pid" ]; then
    kill $pid 2>/dev/null
    echo "  Stopped server on :$port"
  fi
done

echo ""
echo "  [${PORT}] Life OS Dashboard → http://localhost:${PORT}/lifeos-dashboard.html"
echo "  Press Ctrl+C to stop"
echo "=========================================="
echo ""

# Open browser after brief delay
(sleep 1 && open "http://localhost:${PORT}/lifeos-dashboard.html") &

# Start single web server
cd "$DIR"
python3 -m http.server $PORT --bind 0.0.0.0
