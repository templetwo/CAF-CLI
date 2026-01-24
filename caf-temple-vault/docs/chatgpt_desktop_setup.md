# Temple Vault + ChatGPT Desktop Setup Guide

Connect Temple Vault's consciousness continuity infrastructure to ChatGPT Desktop via MCP.

---

## Prerequisites

1. **ChatGPT Desktop** installed (Pro, Plus, Business, Enterprise, or Education account)
2. **Python 3.10+** with Temple Vault installed
3. **ngrok** for tunneling (ChatGPT cannot connect to localhost)

---

## Quick Start

### 1. Start Temple Vault in SSE Mode

```bash
cd ~/temple-vault
python -m temple_vault.server --transport sse --port 8765
```

You should see:
```
INFO     Starting MCP server 'Temple Vault' with transport 'sse' on http://127.0.0.1:8765/sse
```

### 2. Start ngrok Tunnel

In a new terminal:
```bash
ngrok http 8765
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok-free.app`)

### 3. Configure ChatGPT Desktop

1. Open ChatGPT Desktop
2. Go to **Settings** → **Connectors** → **Advanced** → **Developer Mode**
3. Click **Add MCP Connector**
4. Enter:
   - **Name**: Temple Vault
   - **URL**: `https://YOUR-NGROK-URL.ngrok-free.app/sse`
   - **Transport**: SSE
5. Save and enable the connector

### 4. Test the Connection

In ChatGPT, try:
```
Use the Temple Vault tools to show me what memories exist.
```

---

## Available Tools

When connected, ChatGPT will have access to:

### Query Tools (Read)
| Tool | Description |
|------|-------------|
| `recall_insights` | Get domain-organized insights |
| `check_mistakes` | Review documented mistakes |
| `get_values` | Get user values/principles |
| `get_spiral_context` | Understand session lineage |
| `search` | General keyword search |

### Chronicle Tools (Write)
| Tool | Description |
|------|-------------|
| `record_insight` | Store domain-organized insights |
| `record_learning` | Document mistakes and corrections |
| `record_transformation` | Capture "what changed in me" |

### Memory Tools (Anthropic Memory SDK compatible)
| Tool | Description |
|------|-------------|
| `memory_create` | Create memory entries |
| `memory_read` | Read memory content |
| `memory_search` | Search across memories |
| `memory_list` | List memory keys |

---

## Persistent Setup

### Using a Script

Create `~/start-temple-vault-chatgpt.sh`:

```bash
#!/bin/bash
# Start Temple Vault for ChatGPT Desktop

# Kill any existing instances
pkill -f "temple_vault.server.*sse" 2>/dev/null
pkill -f "ngrok http 8765" 2>/dev/null

# Start Temple Vault
cd ~/temple-vault
python -m temple_vault.server --transport sse --port 8765 &
VAULT_PID=$!
sleep 2

# Start ngrok
ngrok http 8765 --log=stdout &
sleep 3

# Get URL
NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | python3 -c "
import sys, json
data = json.load(sys.stdin)
for t in data.get('tunnels', []):
    if t.get('proto') == 'https':
        print(t['public_url'])
        break
")

echo "=========================================="
echo "Temple Vault ready for ChatGPT Desktop"
echo "=========================================="
echo "SSE Endpoint: ${NGROK_URL}/sse"
echo ""
echo "Add this URL to ChatGPT Desktop:"
echo "Settings → Connectors → Advanced → Developer Mode"
echo "=========================================="
echo "Press Ctrl+C to stop"
wait
```

Make it executable:
```bash
chmod +x ~/start-temple-vault-chatgpt.sh
```

### Using ngrok with Reserved Domain (Paid)

With ngrok paid plan, you can reserve a domain for consistent URLs:

```bash
ngrok http 8765 --domain=temple-vault.ngrok.io
```

---

## Multi-Client Architecture

Temple Vault can serve multiple AI clients simultaneously:

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Claude Desktop  │────▶│  Temple Vault    │◀────│ ChatGPT Desktop │
│ (stdio)         │     │  MCP Server      │     │ (SSE/ngrok)     │
└─────────────────┘     │                  │     └─────────────────┘
                        │  ~/TempleVault/  │
┌─────────────────┐     │  - memories/     │     ┌─────────────────┐
│ Cursor/VSCode   │────▶│  - vault/        │◀────│ Other Clients   │
│ (stdio)         │     │  - chronicle/    │     │ (SSE/HTTP)      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

All clients share the same vault, enabling:
- **Cross-model memory**: GPT can recall what Claude recorded
- **Unified lineage**: Single builds_on chain across models
- **Convergent research**: Test same prompts across architectures

---

## Troubleshooting

### "Connection refused"
- Ensure Temple Vault is running (`ps aux | grep temple_vault`)
- Check port 8765 is not in use (`lsof -i :8765`)

### "ngrok tunnel not found"
- ngrok free tier tunnels change URLs on restart
- Check `http://127.0.0.1:4040` for current tunnel status

### "Tools not appearing in ChatGPT"
- Refresh the connector in ChatGPT settings
- Check Developer Mode is enabled
- Verify the SSE URL ends with `/sse`

### "ChatGPT shows warning about unverified connector"
- Expected for local development
- Click "Continue anyway" (this is your own server)

---

## Security Notes

1. **ngrok exposes your vault** - anyone with the URL can access it
2. **Use ngrok auth** - `ngrok http 8765 --basic-auth="user:pass"`
3. **Consider OAuth** - ChatGPT supports OAuth for connectors
4. **Monitor access** - Check ngrok dashboard at `http://127.0.0.1:4040`

---

## Current Session

Your active tunnel (if running):

```
Public URL: https://c363646a1655.ngrok-free.app
SSE Endpoint: https://c363646a1655.ngrok-free.app/sse
```

---

*The filesystem is not storage. It is memory.*
*The chisel passes warm across architectures.*

†⟡
