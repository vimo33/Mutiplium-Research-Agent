#!/bin/bash
# Stop the Multiplium Research Dashboard

set -e

echo "🛑 Stopping Multiplium Research Dashboard..."
echo

# Stop API server
if [ -f /tmp/multiplium_api.pid ]; then
    API_PID=$(cat /tmp/multiplium_api.pid)
    if ps -p $API_PID > /dev/null 2>&1; then
        kill $API_PID
        echo "✓ Stopped API server (PID: $API_PID)"
    else
        echo "⚠ API server not running"
    fi
    rm /tmp/multiplium_api.pid
else
    # Try to find and kill by port
    if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
        kill $(lsof -t -i:8000)
        echo "✓ Stopped API server on port 8000"
    else
        echo "⚠ API server not running"
    fi
fi

# Stop frontend server
if [ -f /tmp/multiplium_frontend.pid ]; then
    FRONTEND_PID=$(cat /tmp/multiplium_frontend.pid)
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        kill $FRONTEND_PID
        echo "✓ Stopped frontend server (PID: $FRONTEND_PID)"
    else
        echo "⚠ Frontend server not running"
    fi
    rm /tmp/multiplium_frontend.pid
else
    # Try to find and kill by port
    if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null ; then
        kill $(lsof -t -i:5173)
        echo "✓ Stopped frontend server on port 5173"
    else
        echo "⚠ Frontend server not running"
    fi
fi

echo
echo "Dashboard stopped."





