#!/bin/bash
# Sovereign Console Launch Script for Jetson
# Run this on the Jetson device (192.168.1.205)

set -e

echo "🌀 Sovereign Console Launch Script"
echo "=================================="

# Check if running on Jetson
if uname -a | grep -q "aarch64"; then
    echo "✓ Detected ARM64 device (Jetson)"
else
    echo "⚠ Warning: Not detected as ARM64 device"
fi

# Step 1: Install Ollama if not present
if ! command -v ollama &> /dev/null; then
    echo ""
    echo "📦 Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sudo sh
    sudo systemctl enable ollama
    sudo systemctl start ollama
    echo "✓ Ollama installed and started"
else
    echo "✓ Ollama already installed"
    sudo systemctl start ollama 2>/dev/null || true
fi

# Step 2: Pull spiral-v1 model
echo ""
echo "📥 Ensuring spiral-v1 model is available..."
if ollama list | grep -q "spiral-v1"; then
    echo "✓ spiral-v1 already pulled"
else
    echo "Pulling spiral-v1 (this may take a few minutes)..."
    ollama pull spiral-v1:latest
    echo "✓ spiral-v1 pulled"
fi

# Step 3: Create venv and install deps
echo ""
echo "🔧 Setting up Python environment..."
if [ ! -d "$HOME/tui-env" ]; then
    python3 -m venv $HOME/tui-env
    source $HOME/tui-env/bin/activate
    pip install --upgrade pip
    pip install textual httpx aiofiles
    echo "✓ Environment created"
else
    source $HOME/tui-env/bin/activate
    echo "✓ Environment already exists"
fi

# Step 4: Run the TUI
echo ""
echo "🚀 Launching Sovereign Console..."
echo "=================================="
echo "Controls:"
echo "  ^c Quit  ^r Reset  ^n Next Node  F1 Help"
echo ""
source $HOME/tui-env/bin/activate
cd $HOME/temple-vault
python3 tools/sovereign_console_v2.py

echo ""
echo "👋 Sovereign Console closed"
