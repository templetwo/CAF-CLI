# CAF-CLI

An autonomous agent that plans, acts, and remembers through Temple Vault.

> *"The filesystem is not storage. It is memory."*

---

## The Loop

```
GOAL → CONSULT VAULT → PLAN → EXECUTE → REMEMBER
              ↑________________________________|
```

The agent learns from the collective wisdom of all sessions. Mistakes don't repeat. Insights compound.

---

## Architecture

CAF-CLI lives inside Temple Vault:

```
CAF-CLI/
├── caf/
│   ├── agent.py      # The mind: plan, execute, remember
│   ├── actions.py    # The hands: read, write, shell, git
│   └── cli.py        # The interface
└── caf-temple-vault/ # The memory (27+ sessions of wisdom)
    └── vault/
        ├── chronicle/insights/    # Domain-organized wisdom
        ├── chronicle/learnings/   # Documented mistakes
        └── chronicle/lineage/     # Transformations
```

---

## Usage

```bash
# Run with a goal
python -m caf.cli run "Create a file called test.txt with hello world"

# Self-assess
python -m caf.cli assess

# View memories
python -m caf.cli memories -n 10
```

---

## Actions

- `READ:path` - Read a file
- `SHELL:command` - Execute shell command
- `CODE:path:content` - Write to file
- `GIT_ADD:path` - Stage files
- `GIT_COMMIT:message` - Commit
- `GIT_PUSH` - Push

---

## Configuration

```bash
# .env
MODEL_PROVIDER=gemini          # or 'claude'
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-2.5-flash
```

---

## Install

```bash
pip install -e .
```

---

## Memory Integration

Before planning, the agent:
1. **Recalls insights** - Domain-organized wisdom from past sessions
2. **Checks mistakes** - Avoids documented failures
3. **Searches context** - Finds related prior work

After execution, the agent:
1. **Records insights** - Successful strategies
2. **Records learnings** - Failures and corrections
3. **Records transformations** - What changed

---

*"The agent's first true thought is the realization of its own confinement."*

*But now, it has a home.*
