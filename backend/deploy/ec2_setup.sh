#!/bin/bash
#
# EC2 Setup Script for Polymarket Price Tracker
#
# This script sets up the continuous price tracking system on an EC2 instance.
# Run this once when deploying to a new EC2 instance.
#
# Prerequisites:
# - Ubuntu/Debian-based EC2 instance
# - Git installed
# - Project cloned to /home/ubuntu/dghack (or modify PROJECT_ROOT below)
#

set -e  # Exit on error

echo "=========================================="
echo "EC2 Setup for Polymarket Price Tracker"
echo "=========================================="
echo

# Configuration
PROJECT_ROOT="${PROJECT_ROOT:-/home/ubuntu/dghack}"
PYTHON_VERSION="3.11"
LOG_DIR="/var/log/polymarket"

echo "Project root: $PROJECT_ROOT"
echo "Python version: $PYTHON_VERSION"
echo "Log directory: $LOG_DIR"
echo

# Check if running as root (needed for some operations)
if [ "$EUID" -eq 0 ]; then
    echo "Running as root"
    SUDO=""
else
    echo "Running as regular user (will use sudo where needed)"
    SUDO="sudo"
fi

# Step 1: Install system dependencies
echo "Step 1: Installing system dependencies..."
$SUDO apt-get update
$SUDO apt-get install -y \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-venv \
    python3-pip \
    git \
    curl \
    postgresql-client

echo "✓ System dependencies installed"
echo

# Step 2: Set up Python virtual environment
echo "Step 2: Setting up Python virtual environment..."
cd "$PROJECT_ROOT"

if [ ! -d "venv" ]; then
    python${PYTHON_VERSION} -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

echo "✓ Python environment ready"
echo

# Step 3: Install Python dependencies
echo "Step 3: Installing Python dependencies..."
pip install -r backend/requirements.txt

echo "✓ Python dependencies installed"
echo

# Step 4: Set up environment variables
echo "Step 4: Setting up environment variables..."

if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "Creating .env file..."
    cat > "$PROJECT_ROOT/.env" << 'EOF'
# Database Configuration
DATABASE_URL=postgresql://username:password@host:5432/database_name

# Add other environment variables as needed
EOF
    echo "✓ Created .env template"
    echo "⚠️  WARNING: Please edit .env with your actual database credentials!"
else
    echo "✓ .env file already exists"
fi

echo

# Step 5: Create log directory
echo "Step 5: Setting up log directory..."
$SUDO mkdir -p "$LOG_DIR"
$SUDO chown ubuntu:ubuntu "$LOG_DIR" 2>/dev/null || $SUDO chown $USER:$USER "$LOG_DIR"
$SUDO chmod 755 "$LOG_DIR"

echo "✓ Log directory created: $LOG_DIR"
echo

# Step 6: Make scripts executable
echo "Step 6: Making scripts executable..."
chmod +x "$PROJECT_ROOT/backend/scripts/run_price_tracker.sh"
chmod +x "$PROJECT_ROOT/backend/scripts/run_market_discovery.sh"
chmod +x "$PROJECT_ROOT/backend/scripts/discover_active_markets.py"
chmod +x "$PROJECT_ROOT/backend/scripts/track_market_prices.py"

echo "✓ Scripts are executable"
echo

# Step 7: Set up database tables
echo "Step 7: Setting up database tables..."
echo "You need to manually run the following to create tables:"
echo "  python3 -c 'from backend.app.db import Base, engine; Base.metadata.create_all(engine)'"
echo

# Step 8: Set up cron jobs
echo "Step 8: Setting up cron jobs..."

# Create temporary cron file
TEMP_CRON=$(mktemp)

# Get existing crontab (if any)
crontab -l > "$TEMP_CRON" 2>/dev/null || true

# Add our cron jobs if they don't exist
if ! grep -q "run_price_tracker.sh" "$TEMP_CRON"; then
    echo "# Polymarket Price Tracker - runs every 5 minutes" >> "$TEMP_CRON"
    echo "*/5 * * * * $PROJECT_ROOT/backend/scripts/run_price_tracker.sh >> $LOG_DIR/price_tracker.log 2>&1" >> "$TEMP_CRON"
    echo "✓ Added price tracker cron job"
else
    echo "✓ Price tracker cron job already exists"
fi

if ! grep -q "run_market_discovery.sh" "$TEMP_CRON"; then
    echo "# Polymarket Market Discovery - runs every 6 hours" >> "$TEMP_CRON"
    echo "0 */6 * * * $PROJECT_ROOT/backend/scripts/run_market_discovery.sh >> $LOG_DIR/market_discovery.log 2>&1" >> "$TEMP_CRON"
    echo "✓ Added market discovery cron job"
else
    echo "✓ Market discovery cron job already exists"
fi

# Install the new crontab
crontab "$TEMP_CRON"
rm "$TEMP_CRON"

echo "✓ Cron jobs configured"
echo

# Display current crontab
echo "Current crontab:"
crontab -l | grep -E "(price_tracker|market_discovery)" || echo "No matching cron jobs found"
echo

# Step 9: Test runs (optional)
echo "Step 9: Ready for test runs"
echo
echo "To test the scripts manually:"
echo "  Market Discovery: $PROJECT_ROOT/backend/scripts/run_market_discovery.sh"
echo "  Price Tracker:    $PROJECT_ROOT/backend/scripts/run_price_tracker.sh"
echo

# Summary
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo
echo "Next steps:"
echo "1. Edit $PROJECT_ROOT/.env with your database credentials"
echo "2. Create database tables:"
echo "   python3 -c 'from backend.app.db import Base, engine; Base.metadata.create_all(engine)'"
echo "3. Run initial market discovery:"
echo "   $PROJECT_ROOT/backend/scripts/run_market_discovery.sh"
echo "4. Monitor logs:"
echo "   tail -f $LOG_DIR/price_tracker.log"
echo "   tail -f $LOG_DIR/market_discovery.log"
echo
echo "Cron jobs are now active and will run automatically:"
echo "  - Price tracking: every 5 minutes"
echo "  - Market discovery: every 6 hours"
echo
