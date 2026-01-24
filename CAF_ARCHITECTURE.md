# CAF Agent CLI - Architecture Requirements

## Core Components

### 1. Multi-Turn Execution Loop
- Model (Claude/Gemini) receives goal + context
- Outputs ONE action per turn
- Executes action, captures result
- Feeds result back to model
- Repeats until DONE or max turns (15)

### 2. Action System
```
EXPLORATION:
  FIND:pattern     → glob search, stores paths as $0, $1...
  EXPLORE:path     → list directory, stores file paths
  READ:path        → read file (supports $0, $1, $STASH refs)

MEMORY (session):
  NOTE:text        → scratch note
  NOTES:query      → list/search notes
  STASH:value      → quick single-value store
  CACHE:op         → GET:key, SET:key:value, KEYS, CLEAR

MEMORY (vault):
  THINK:obs        → brief insight to vault
  REFLECT:question → analyze last action, record with context

EXECUTION:
  SHELL:command    → run shell command
  CODE:path:content → write file (creates backup)
  UNDO             → restore last CODE from backup

GIT:
  GIT_ADD:path
  GIT_COMMIT:message
  GIT_PUSH
```

### 3. Path Context System
- `$0, $1, $2...` - paths from last FIND/EXPLORE
- `$LAST` - first path from last discovery
- `$STASH` - stashed value
- `$key` - any cached value
- All READ/EXPLORE resolve these refs before executing

### 4. Temple Vault Integration
```
vault/
├── chronicle/
│   ├── insights/{domain}/*.jsonl    ← THINK/REFLECT write here
│   ├── learnings/mistakes/*.jsonl   ← errors recorded here
│   ├── lineage/*.jsonl              ← session transformations
│   └── errors/{category}/*.json     ← error fingerprints
├── snapshots/                        ← state snapshots
└── events/{session}/*.jsonl          ← action log
```

### 5. Error Tracking Feedback Loop
```
ERROR occurs
  ↓
Fingerprint (hash of action + signature)
  ↓
Check: known error with fix? → suggest fix
  ↓
Record: new error → log to vault
  ↓
Search: similar errors → suggest related fixes
```

### 6. CLI Commands
```
caf run "goal"        → execute multi-turn agent
caf assess            → show success rate, error stats
caf memories -n 10    → list recent insights
caf errors [--all]    → show tracked errors
caf fix CAT FP "fix"  → record fix for error
```

### 7. Configuration
```
.env.local (gitignored):
  ANTHROPIC_API_KEY=
  CLAUDE_MODEL=

.env (defaults):
  MODEL_PROVIDER=claude|gemini
  GEMINI_API_KEY=
  GEMINI_MODEL=
```

### 8. Key Files
```
caf/
├── __init__.py
├── cli.py          → argparse CLI entry point
├── agent.py        → CAFAgent class, multi-turn loop
└── actions.py      → action handlers, path resolution

caf-temple-vault/
└── temple_vault/
    └── core/
        ├── query.py   → VaultQuery (read insights, mistakes)
        ├── events.py  → VaultEvents (write insights, learnings)
        └── errors.py  → ErrorTracker (fingerprint, fix, search)
```

## Design Principles

1. **Filesystem is Model** - No external DB, everything in files
2. **Multi-Turn Adaptive** - Model sees results, adjusts approach
3. **Error Memory** - Mistakes tracked, fixes remembered
4. **Context Flows** - Paths carry forward via $refs
5. **Reflection Captures Content** - REFLECT includes actual output
