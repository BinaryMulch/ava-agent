#!/bin/bash
# Ava Agent - Installation Script
# Run as root on Ubuntu/Debian

set -e

# ── Colors ─────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── Check root ─────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    error "Please run as root: sudo bash install.sh"
fi

# ── Determine install directory ────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR"
info "Installing from: $INSTALL_DIR"

# ── Install system dependencies ────────────────────────
info "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git > /dev/null

# ── Create virtual environment ─────────────────────────
info "Setting up Python virtual environment..."
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
fi

# ── Install Python dependencies ────────────────────────
info "Installing Python packages..."
"$INSTALL_DIR/venv/bin/pip" install -q -r "$INSTALL_DIR/requirements.txt"

# ── Create .env file if it doesn't exist ───────────────
if [ ! -f "$INSTALL_DIR/.env" ]; then
    info "Creating .env file..."
    cat > "$INSTALL_DIR/.env" << 'EOF'
# xAI Grok API Key (required)
XAI_API_KEY=your-api-key-here

# xAI API settings
XAI_BASE_URL=https://api.x.ai/v1
XAI_MODEL=grok-4-1-fast-reasoning

# Server settings
AVA_HOST=127.0.0.1
AVA_PORT=8888

# Service name (for systemd)
AVA_SERVICE_NAME=ava-agent

# Command timeout in seconds
AVA_COMMAND_TIMEOUT=300
EOF
    warn "Please edit $INSTALL_DIR/.env and set your XAI_API_KEY"
fi

# ── Create data directory ──────────────────────────────
mkdir -p "$INSTALL_DIR/data"

# ── Create systemd service ─────────────────────────────
info "Creating systemd service..."
cat > /etc/systemd/system/ava-agent.service << EOF
[Unit]
Description=Ava Agent - AI System Assistant
After=network.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python -m uvicorn server:app --host \${AVA_HOST} --port \${AVA_PORT}
Restart=always
RestartSec=5

# Run as root for full system access
User=root
Group=root

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ava-agent

[Install]
WantedBy=multi-user.target
EOF

# ── Enable and start ───────────────────────────────────
systemctl daemon-reload
systemctl enable ava-agent

info "Installation complete!"
echo ""
echo "──────────────────────────────────────────────────"
echo "  Next steps:"
echo "  1. Edit your API key:  nano $INSTALL_DIR/.env"
echo "  2. Start the agent:    systemctl start ava-agent"
echo "  3. Check status:       systemctl status ava-agent"
echo "  4. View logs:          journalctl -u ava-agent -f"
echo "  5. Open in browser:    http://127.0.0.1:8888"
echo "──────────────────────────────────────────────────"
