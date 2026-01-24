#!/bin/bash
#
# Deploy Voice Engine to Mac Studio
#
# Usage:
#   ./deploy_studio.sh
#
# Prerequisites:
#   - SSH access to tony_studio@192.168.1.195
#   - Python 3.10+ on Mac Studio
#

set -e

STUDIO_HOST="tony_studio@192.168.1.195"
STUDIO_PATH="~/temple-vault-voice"
LOCAL_VOICE_DIR="$(dirname "$0")"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║           Temple Vault Voice - Mac Studio Deploy              ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Create remote directory
echo "[1/5] Creating remote directory..."
ssh "$STUDIO_HOST" "mkdir -p $STUDIO_PATH"

# Step 2: Copy voice module
echo "[2/5] Copying voice module..."
scp -r "$LOCAL_VOICE_DIR"/*.py "$STUDIO_HOST:$STUDIO_PATH/"

# Step 3: Install dependencies
echo "[3/5] Installing dependencies..."
ssh "$STUDIO_HOST" "pip install --quiet aiohttp httpx soundfile 2>/dev/null || pip3 install --quiet aiohttp httpx soundfile"

# Step 4: Check for qwen-tts (may need manual install)
echo "[4/5] Checking for qwen-tts..."
ssh "$STUDIO_HOST" "python3 -c 'import qwen_tts; print(\"qwen-tts OK\")' 2>/dev/null || echo 'WARNING: qwen-tts not installed. Run: pip install qwen-tts'"

# Step 5: Create systemd service (optional)
echo "[5/5] Creating service file..."
ssh "$STUDIO_HOST" "cat > ~/voice-server.service << 'EOF'
[Unit]
Description=Temple Vault Voice Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$STUDIO_PATH
ExecStart=/usr/bin/python3 -m voice.server --port 8765
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Deployment complete!"
echo ""
echo "  To start manually:"
echo "    ssh $STUDIO_HOST"
echo "    cd $STUDIO_PATH && python3 -m voice.server"
echo ""
echo "  To install as service (requires sudo):"
echo "    sudo cp ~/voice-server.service /etc/systemd/system/"
echo "    sudo systemctl enable voice-server"
echo "    sudo systemctl start voice-server"
echo ""
echo "  Test from Jetson:"
echo "    curl http://192.168.1.195:8765/health"
echo "═══════════════════════════════════════════════════════════════"
