#!/bin/bash
#
# Wrapper script for price tracking service
# Runs every 5 minutes via cron
#
# Cron entry:
# */5 * * * * /path/to/dghack/backend/scripts/run_price_tracker.sh >> /var/log/price_tracker.log 2>&1
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
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting price tracker..."

# Run the price tracking script
python3 "$PROJECT_ROOT/backend/scripts/track_market_prices.py"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Price tracker completed successfully"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Price tracker failed with exit code $EXIT_CODE" >&2
fi

exit $EXIT_CODE
