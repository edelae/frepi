#!/usr/bin/env bash
# Shared deploy script for Frepi services
# Usage: bash /opt/deploy/deploy.sh <frepi-agent|frepi-finance>
#
# This script is placed at /opt/deploy/deploy.sh on the VM.
# It pulls the latest code from GitHub, installs dependencies,
# updates the systemd service file, and restarts the service.

set -euo pipefail

SERVICE="$1"
LOGFILE="/opt/deploy/deploy.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

log() {
    echo "[$TIMESTAMP] $SERVICE: $1" | tee -a "$LOGFILE"
}

case "$SERVICE" in
    frepi-agent)
        REPO_DIR="/opt/frepi-agent/repo"
        VENV_DIR="/opt/frepi-agent/venv"
        REPO_URL="https://github.com/edelae/frepi.git"
        SERVICE_FILE="deploy/frepi-agent.service"
        ;;
    frepi-finance)
        REPO_DIR="/opt/frepi-finance/repo"
        VENV_DIR="/opt/frepi-finance/venv"
        REPO_URL="https://github.com/edelae/frepi_finance_bot.git"
        SERVICE_FILE="deploy/frepi-finance.service"
        ;;
    *)
        echo "Usage: $0 <frepi-agent|frepi-finance>"
        exit 1
        ;;
esac

log "Starting deployment"

# Ensure deploy log directory exists
mkdir -p /opt/deploy

# Pull latest code
if [ ! -d "$REPO_DIR/.git" ]; then
    log "Cloning repository..."
    git clone "$REPO_URL" "$REPO_DIR"
else
    log "Pulling latest changes..."
    cd "$REPO_DIR"
    git fetch origin main
    BEFORE=$(git rev-parse HEAD)
    git reset --hard origin/main
    AFTER=$(git rev-parse HEAD)
    if [ "$BEFORE" = "$AFTER" ]; then
        log "No new changes (already at $AFTER)"
    else
        log "Updated $BEFORE -> $AFTER"
    fi
fi

cd "$REPO_DIR"

# Install dependencies
log "Installing dependencies..."
"$VENV_DIR/bin/pip" install --quiet -r requirements.txt
"$VENV_DIR/bin/pip" install --quiet -e .

# Update systemd service file if changed
if [ -f "$SERVICE_FILE" ]; then
    if ! diff -q "$SERVICE_FILE" "/etc/systemd/system/${SERVICE}.service" >/dev/null 2>&1; then
        log "Updating systemd service file..."
        cp "$SERVICE_FILE" "/etc/systemd/system/${SERVICE}.service"
        systemctl daemon-reload
    fi
fi

# Restart service
log "Restarting ${SERVICE}..."
systemctl restart "$SERVICE"

# Health check — wait up to 10 seconds for service to stabilize
sleep 3
if systemctl is-active --quiet "$SERVICE"; then
    log "Deployment successful - service is active"
else
    log "ERROR: Service failed to start!"
    journalctl -u "$SERVICE" --no-pager -n 20 >> "$LOGFILE" 2>&1
    exit 1
fi

log "Deployment complete"
