#!/bin/bash
#
# Wrapper script for market discovery service
# Runs every 6 hours via cron
#
# Cron entry:
# 0 */6 * * * /path/to/dghack/backend/scripts/run_market_discovery.sh >> /var/log/market_discovery.log 2>&1
#

set -e  # Exit on error

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Change to project root
cd "$PROJECT_ROOT"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(cat "$PROJECT_ROOT/.env" | grep -v '^#' | xargs)
fi

# Activate virtual environment if it exists
if [ -d "$PROJECT_ROOT/venv" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Log start time
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting market discovery..."

# Run the market discovery script
python3 "$PROJECT_ROOT/backend/scripts/discover_active_markets.py"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Market discovery completed successfully"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Market discovery failed with exit code $EXIT_CODE" >&2
fi

exit $EXIT_CODE
