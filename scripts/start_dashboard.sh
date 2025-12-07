#!/bin/bash
# Start the Multiplium Research Dashboard
# This script starts both the API server and the frontend dev server

set -e

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKSPACE_ROOT"

echo "🚀 Starting Multiplium Research Dashboard..."
echo

# Check if API server is already running
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "✓ API server already running on port 8000"
else
    echo "Starting API server on port 8000..."
    cd "$WORKSPACE_ROOT"
    python3 -m uvicorn servers.research_dashboard:app --host 0.0.0.0 --port 8000 --reload > logs/api_server.log 2>&1 &
    API_PID=$!
    echo "$API_PID" > /tmp/multiplium_api.pid
    echo "✓ API server started (PID: $API_PID)"
    echo "  Logs: logs/api_server.log"
fi

# Check if frontend is already running
if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null ; then
    echo "✓ Frontend already running on port 5173"
else
    echo "Starting frontend dev server on port 5173..."
    cd "$WORKSPACE_ROOT/dashboard"
    npm run dev > ../logs/frontend_dev.log 2>&1 &
    FRONTEND_PID=$!
    echo "$FRONTEND_PID" > /tmp/multiplium_frontend.pid
    echo "✓ Frontend started (PID: $FRONTEND_PID)"
    echo "  Logs: logs/frontend_dev.log"
fi

echo
echo "======================================"
echo "Dashboard is ready!"
echo "======================================"
echo
echo "  Frontend: http://localhost:5173"
echo "  API:      http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo
echo "To stop the dashboard:"
echo "  ./scripts/stop_dashboard.sh"
echo

# Wait a bit for servers to start
sleep 3

# Open browser (optional, comment out if you don't want auto-open)
if command -v open &> /dev/null; then
    open http://localhost:5173
fi





