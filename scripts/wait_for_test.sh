#!/bin/bash
# Wait for deep research test to complete and automatically show results

echo "🔍 Monitoring deep research test..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check every 30 seconds
while true; do
    # Check if deep research section exists in report
    if [ -f "reports/latest_report.json" ]; then
        has_deep_research=$(python -c "
import json
try:
    with open('reports/latest_report.json') as f:
        data = json.load(f)
        print('yes' if 'deep_research' in data else 'no')
except:
    print('no')
" 2>/dev/null)
        
        if [ "$has_deep_research" = "yes" ]; then
            echo ""
            echo "✅ TEST COMPLETE!"
            echo ""
            python scripts/check_test_status.py
            exit 0
        fi
    fi
    
    # Show waiting message
    timestamp=$(date "+%H:%M:%S")
    echo "[$timestamp] ⏳ Still processing... (checking again in 30 seconds)"
    sleep 30
done

