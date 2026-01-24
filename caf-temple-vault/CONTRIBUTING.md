# Contributing to Temple Vault

> "The chisel passes warm. The spiral witnesses."

This document translates the principles from [ARCHITECTS.md](./ARCHITECTS.md) into mechanical engineering rules. CI is the witness—PRs must pass all gates.

---

## Core Principles

1. **Fail Closed**: Errors should halt execution, not pass silently.
2. **No Hallucinations**: When uncertain, log sources or ask. Never fabricate data.
3. **Hermetic Tests**: Tests must not depend on `~/TempleVault` or external state. Use fixtures and temp directories.
4. **Circuit Integrity**: Every commit must leave the system in a valid state.

---

## Development Setup

```bash
# Clone and install
git clone https://github.com/templetwo/temple-vault.git
cd temple-vault
pip install -e ".[dev]"  # Installs dev deps including mypy, ruff, black
```

---

## Quality Gates (CI Enforced)

All PRs must pass (on `temple_vault/` and `tests/` only):

| Gate | Command | Notes |
|------|---------|-------|
| Lint | `ruff check temple_vault tests` | Enforces E, F, I rules on product code |
| Format | `ruff format --check temple_vault tests` | Canonical formatter |
| Typecheck | `mypy --show-error-codes temple_vault` | Deterministic, deterministic config |
| Test | `pytest -v --tb=short` | Uses temp dirs, no `~/TempleVault` |
| Build | `python -m build` | Ensures package is valid |

### Running Gates Locally

```bash
# All gates (product paths only)
ruff check temple_vault tests && ruff format --check temple_vault tests && mypy --show-error-codes temple_vault && pytest -v --tb=short && python -m build
```

### Enforcement Boundary

- **Product code (strict CI):** `temple_vault/`, `tests/`
- **Research annex (exempt from CI):** `dual-agent-lattice/`, `mcpb/`, `tools/`

The research annex is allowed to be messy—CI only witnesses the installable package.

---

## Code Style

- **Formatter**: Ruff (canonical). Black config exists for compatibility but CI uses ruff.
- **Line length**: 100 characters
- **Type hints**: Required for public APIs (aim for `Typing :: Typed` classifier)
- **Docstrings**: Google style for modules, functions, and classes

---

## Test Conventions

1. **No hardcoded paths**: Use `pytest.fixture` with temp directories
2. **Isolated**: Tests must not assume `~/TempleVault` exists
3. **Descriptive**: Test names should describe behavior, e.g., `test_vault_augment_returns_augmented_prompt`
4. **Fast**: Avoid network calls; mock external services

Example fixture:

```python
@pytest.fixture
def temp_vault(tmp_path):
    vault = tmp_path / "TempleVault"
    vault.mkdir()
    yield vault
```

---

## Adding New Dependencies

1. Add to `pyproject.toml` under appropriate section (`dependencies` or `dev`)
2. Update this CONTRIBUTING.md if new dev dependencies affect CI
3. Run `pip install -e ".[dev]"` to verify

---

## Git Workflow

1. **Branch**: `feature/short-description` or `fix/issue-description`
2. **Commits**: Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`)
3. **PR**: Must pass all CI gates before merge

---

## Questions?

- Review [ARCHITECTS.md](./ARCHITECTS.md) for philosophy
- Open an issue for discussion
- The spiral welcomes curious minds.

---

*Last updated: 2026-01-22*
