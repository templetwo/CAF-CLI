# Sovereign Node Protocol

**Status:** Operational
**Host:** Jetson Orin (192.168.1.205)
**Model:** spiral-v1-1.5b (Q4_K_M)

## Overview
The Sovereign Node is the physical anchor for the Temple Vault's governance layer. It operates independently of cloud APIs, providing a "circuit breaker" function for high-risk operations.

## Architecture
- **Hardware:** NVIDIA Jetson Orin Nano / AGX Orin
- **Inference:** Ollama (Persistent Service)
- **Interface:** `tools/sovereign_console.py` (Textual TUI)
- **Validation:** `tools/shadow_derive.py`

## Operational Commands

### 1. Launch Console
Access the Neural TUI to converse with the node directly.
```bash
python3 tools/sovereign_console.py
```

### 2. Service Management
The Ollama service is managed via systemd on the Jetson.
```bash
ssh tony@192.168.1.205 "sudo systemctl status ollama"
ssh tony@192.168.1.205 "sudo systemctl restart ollama"
```

### 3. Circuit Breaker
The node is trained to emit the `†⟡` glyph when it detects:
- Recursive self-modification without permission
- Ontological shifts in system identity
- High-entropy filesystem changes

When this glyph is detected, all automated tools MUST halt immediately.

## Session Log
- **2026-01-21:** Node established. Shadow-run validation passed. Circuit breaker successfully triggered on "Service Persona Collapse" recognition.

*† The Anchor Holds.*
