# Temple Vault Namespace Sync

## The Issue

Two parallel namespaces existed:
- `vault/chronicle/` - where `record_insight`, `record_transformation` write
- `memories/experiential/` - where `memory_list`, `memory_read` look

This caused data written via chronicle tools to be invisible to memory tools.

## The Fix

Symlinks unify the namespaces:

```bash
cd ~/TempleVault/memories/experiential
ln -sf ../../vault/chronicle/insights insights
ln -sf ../../vault/chronicle/lineage transformations
```

## Current Structure

```
~/TempleVault/
├── vault/
│   └── chronicle/
│       ├── insights/      ← canonical location
│       └── lineage/       ← canonical location
└── memories/
    └── experiential/
        ├── insights       → ../../vault/chronicle/insights (symlink)
        └── transformations → ../../vault/chronicle/lineage (symlink)
```

## Verification

```bash
# Both should return the same data
cat ~/TempleVault/vault/chronicle/insights/architecture/sess_20260120.jsonl
cat ~/TempleVault/memories/experiential/insights/architecture/sess_20260120.jsonl
```

---
*Fixed: 2026-01-20*
