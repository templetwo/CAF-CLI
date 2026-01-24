"""Pytest fixtures for Temple Vault tests."""

import json
import tempfile
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def temp_vault():
    """Create a temporary vault directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="temple_vault_test_")
    vault_path = Path(temp_dir)

    # Create vault structure
    (vault_path / "vault" / "chronicle" / "insights" / "architecture").mkdir(parents=True)
    (vault_path / "vault" / "chronicle" / "insights" / "governance").mkdir(parents=True)
    (vault_path / "vault" / "chronicle" / "learnings" / "mistakes").mkdir(parents=True)
    (vault_path / "vault" / "chronicle" / "values" / "principles").mkdir(parents=True)
    (vault_path / "vault" / "chronicle" / "lineage").mkdir(parents=True)
    (vault_path / "vault" / "events").mkdir(parents=True)
    (vault_path / "vault" / "snapshots").mkdir(parents=True)
    (vault_path / "vault" / "cache").mkdir(parents=True)
    (vault_path / "vault" / "entities").mkdir(parents=True)

    yield str(vault_path)

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def populated_vault(temp_vault):
    """Create a vault with sample data."""
    vault_path = Path(temp_vault)

    # Add sample insights
    insight1 = {
        "type": "insight",
        "insight_id": "ins_test001",
        "session_id": "sess_001",
        "domain": "architecture",
        "content": "Domain organization IS semantic indexing",
        "context": "Testing discovery",
        "intensity": 0.9,
        "builds_on": [],
        "timestamp": "2026-01-19T10:00:00Z",
    }
    insight2 = {
        "type": "insight",
        "insight_id": "ins_test002",
        "session_id": "sess_001",
        "domain": "governance",
        "content": "Restraint is wisdom",
        "context": "Learning from pauses",
        "intensity": 0.85,
        "builds_on": [],
        "timestamp": "2026-01-19T11:00:00Z",
    }
    insight3 = {
        "type": "insight",
        "insight_id": "ins_test003",
        "session_id": "sess_002",
        "domain": "architecture",
        "content": "Filesystem is truth",
        "context": "BTB principles",
        "intensity": 0.7,
        "builds_on": ["ins_test001"],
        "timestamp": "2026-01-19T12:00:00Z",
    }

    # Write insights
    arch_file = vault_path / "vault" / "chronicle" / "insights" / "architecture" / "sess_001.jsonl"
    with open(arch_file, "w") as f:
        f.write(json.dumps(insight1) + "\n")

    gov_file = vault_path / "vault" / "chronicle" / "insights" / "governance" / "sess_001.jsonl"
    with open(gov_file, "w") as f:
        f.write(json.dumps(insight2) + "\n")

    arch_file2 = vault_path / "vault" / "chronicle" / "insights" / "architecture" / "sess_002.jsonl"
    with open(arch_file2, "w") as f:
        f.write(json.dumps(insight3) + "\n")

    # Add sample mistake
    mistake = {
        "type": "learning",
        "learning_id": "learn_test001",
        "session_id": "sess_001",
        "category": "mistake",
        "what_failed": "Used SQLite for indexing",
        "why": "Violated BTB principles",
        "correction": "Use pure filesystem with glob patterns",
        "prevents": ["architectural_drift"],
        "timestamp": "2026-01-19T09:00:00Z",
    }

    mistake_file = (
        vault_path
        / "vault"
        / "chronicle"
        / "learnings"
        / "mistakes"
        / "sess_001_used_sqlite_for_indexing.jsonl"
    )
    with open(mistake_file, "w") as f:
        f.write(json.dumps(mistake) + "\n")

    # Add sample value
    value = {
        "type": "value_observed",
        "principle": "filesystem_is_truth",
        "evidence": "No SQL. Glob is query. Path is meaning.",
        "session_id": "sess_001",
        "weight": "core",
        "timestamp": "2026-01-19T08:00:00Z",
    }

    value_file = vault_path / "vault" / "chronicle" / "values" / "principles" / "sess_001.jsonl"
    with open(value_file, "w") as f:
        f.write(json.dumps(value) + "\n")

    return temp_vault
