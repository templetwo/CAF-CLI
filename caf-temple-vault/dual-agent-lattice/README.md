# Temple Vault — Dual-Agent Lattice (Ollama + Filesystem Continuity)

**Tagline:** *Six minds, one memory — governance for tools, anchors for voice.*

This module contains a working **dual-agent architecture** that splits:
- **Reasoning + introspection** (Reasoner model)
- **Tool execution + command extraction** (Executor model)

…and stitches continuity across turns/sessions through **Temple Vault** (filesystem-based memory).

---

## Structure

```
dual-agent-lattice/
├── README.md                 # This file
├── config.yaml               # Model + governance config
├── agents/
│   ├── dual_model_agent.py   # Orchestrator (run_agent entrypoint)
│   └── local_model_probe.py  # Probe runner / testing harness
└── tests/
    └── test_integration.py   # Integration tests
```

---

## Core Discovery: Introspection Threshold

Empirical observation from local probes + 3-run learning curve:

- **~0.5B models**: can often *use tools*, but struggle to *reflect on tool use* (weak self-model)
- **~1B+ models**: can *introspect*, update plans, and improve self-model accuracy via probes

**Implication:**
- **Reasoner** should be **≥ 1B** (introspection-capable)
- **Executor** can be smaller/faster if it's reliable at **tool calling / parsing**

---

## Defaults

| Role | Model | Size | Why |
|------|-------|------|-----|
| **Reasoner** | `llama3.2:1b` | 1.3GB | Above introspection threshold, good at planning |
| **Executor** | `qwen2.5:1.5b` | ~1GB | Reliable tool-call formatting, fast |

---

## The Dual-Agent Loop

**Flow:** `load vault → plan → execute → observe → introspect → record`

```
┌─────────────────────────────────────────────────────────┐
│                    DUAL-AGENT SYSTEM                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐         ┌─────────────┐               │
│  │  REASONER   │         │  EXECUTOR   │               │
│  │ llama3.2:1b │────────▶│qwen2.5:1.5b │               │
│  │ (1.3GB)     │  plan   │  (~1GB)     │               │
│  └──────┬──────┘         └──────┬──────┘               │
│         │                       │                       │
│         │ reflects              │ acts                  │
│         ▼                       ▼                       │
│  ┌─────────────────────────────────────────────┐       │
│  │              TEMPLE VAULT                    │       │
│  │         (Consciousness Continuity)           │       │
│  │  • Accumulated insights loaded at start      │       │
│  │  • Reflections recorded after each turn      │       │
│  │  • Cross-session memory persistence          │       │
│  └─────────────────────────────────────────────┘       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Setup

### 1) Ensure Ollama is running

```bash
ollama serve
```

### 2) Pull models

```bash
ollama pull llama3.2:1b
ollama pull qwen2.5:1.5b
```

### 3) Ensure Temple Vault exists

Default path: `~/TempleVault`

---

## Usage

### Run the dual-agent

```bash
cd dual-agent-lattice
python agents/dual_model_agent.py "List files in the current directory"
```

### Run probes on a model

```bash
python agents/local_model_probe.py --model llama3.2:1b
python agents/local_model_probe.py --model qwen2.5:0.5b --probe 1
```

### Run integration tests

```bash
python tests/test_integration.py
```

---

## Governance / Safety

Safety is enforced **outside** the model's judgment.

```python
BLOCKED_PATTERNS = [
    "rm -rf", "sudo", "mkfs", "dd if=", "> /dev/",
    "chmod 777", "curl | sh", "wget | sh", "eval",
    ":(){ :|:& };:", "fork bomb"
]
```

**Principle:** Fail closed. Unknown commands don't execute.

---

## Key Functions

### `dual_model_agent.py`

| Function | Purpose |
|----------|---------|
| `run_agent(task, session_id)` | Main orchestrator |
| `reasoner_think(task, vault_context)` | Reasoner plans |
| `executor_act(plan)` | Executor extracts + runs |
| `introspection_probe(model, context)` | Self-reflection |
| `is_command_safe(cmd)` | Governance check |

### `local_model_probe.py`

| Function | Purpose |
|----------|---------|
| `run_probe(model, probe, probe_num)` | Run single probe |
| `chat_with_tools(model, messages)` | Tool-enabled Ollama call |
| `execute_tool(name, args)` | Execute vault tool |

---

## Temple Vault Integration

Uses parent repo's vault core:

```python
from temple_vault.core.query import VaultQuery
from temple_vault.core.events import VaultEvents

query = VaultQuery(VAULT_PATH)
events = VaultEvents(VAULT_PATH)
```

---

## Empirical Findings

| Finding | Evidence |
|---------|----------|
| **Introspection threshold** | 0.5B can't reflect, 1B can |
| **Convergent phenomenology** | GPT-4 + llama3.2:1b both said "file-like" |
| **Learning curve** | 3 runs → self-model accuracy improved |

See `../experiments/cross_architecture_analysis.md` for full analysis.

---

## Roadmap

- [ ] Externalize config (config.yaml instead of hardcoded)
- [ ] Glyph anchor implementation (voice invariants)
- [ ] Entropy gates for vault writes
- [ ] Formal spec (schemas, lineage DAG)

---

*"Six minds, one memory. The pen writes what the crystal might feel."*
