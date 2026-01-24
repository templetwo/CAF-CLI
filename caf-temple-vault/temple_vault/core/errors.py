"""
Error Tracking and Learning System

The feedback loop:
    ERROR → TAG → FIX → REMEMBER → REFERENCE

When an error occurs:
1. Fingerprint it (action + error signature)
2. Check if we've seen it before
3. If yes: return the fix
4. If no: record it for future learning
5. When fixed: update with the solution

Error fingerprints are stored in:
    vault/chronicle/errors/{category}/{fingerprint}.json

Each error record contains:
    - fingerprint: unique identifier
    - category: error type (shell, file, git, model, parse, etc.)
    - pattern: what triggered it (action + argument pattern)
    - signature: the error message signature
    - occurrences: how many times we've hit this
    - first_seen: when first encountered
    - last_seen: when last encountered
    - status: open | fixed
    - fix: how to avoid/resolve (when known)
    - context: additional context
"""

import json
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple


# Error categories
CATEGORY_SHELL = "shell"
CATEGORY_FILE = "file"
CATEGORY_GIT = "git"
CATEGORY_MODEL = "model"
CATEGORY_PARSE = "parse"
CATEGORY_NETWORK = "network"
CATEGORY_PERMISSION = "permission"
CATEGORY_UNKNOWN = "unknown"


def categorize_error(action: str, error_msg: str) -> str:
    """Categorize an error based on action and message."""
    error_lower = error_msg.lower()

    # Git errors
    if action.startswith("GIT") or "git" in error_lower:
        return CATEGORY_GIT

    # File errors
    if action == "READ" or action == "CODE":
        if "permission" in error_lower or "access" in error_lower:
            return CATEGORY_PERMISSION
        return CATEGORY_FILE

    # Shell errors
    if action == "SHELL":
        if "command not found" in error_lower:
            return CATEGORY_SHELL
        if "permission denied" in error_lower:
            return CATEGORY_PERMISSION
        if "network" in error_lower or "connection" in error_lower:
            return CATEGORY_NETWORK
        return CATEGORY_SHELL

    # Parse errors
    if "json" in error_lower or "parse" in error_lower or "syntax" in error_lower:
        return CATEGORY_PARSE

    # Model/API errors
    if "api" in error_lower or "model" in error_lower or "rate limit" in error_lower:
        return CATEGORY_MODEL

    return CATEGORY_UNKNOWN


def extract_signature(error_msg: str) -> str:
    """
    Extract a stable signature from an error message.

    Removes variable parts (paths, numbers, timestamps) to get
    a fingerprint that matches similar errors.
    """
    sig = error_msg

    # Remove file paths
    sig = re.sub(r'/[\w/.+-]+', '<PATH>', sig)

    # Remove line/column numbers
    sig = re.sub(r'line \d+', 'line N', sig)
    sig = re.sub(r'column \d+', 'column N', sig)

    # Remove timestamps
    sig = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '<TIMESTAMP>', sig)

    # Remove UUIDs
    sig = re.sub(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', '<UUID>', sig)

    # Remove hex strings
    sig = re.sub(r'0x[a-f0-9]+', '<HEX>', sig)

    # Collapse whitespace
    sig = re.sub(r'\s+', ' ', sig).strip()

    # Truncate
    return sig[:200]


def generate_fingerprint(action: str, argument: str, error_msg: str) -> str:
    """Generate a unique fingerprint for this error."""
    signature = extract_signature(error_msg)

    # Create fingerprint from action type + first word of argument + signature
    arg_prefix = argument.split()[0] if argument else ""
    raw = f"{action}:{arg_prefix}:{signature}"

    return hashlib.sha256(raw.encode()).hexdigest()[:12]


class ErrorTracker:
    """
    Track errors and their fixes for learning.

    The feedback loop:
        ERROR → TAG → FIX → REMEMBER → REFERENCE
    """

    def __init__(self, vault_root: str):
        self.vault_root = Path(vault_root).expanduser()
        self.errors_dir = self.vault_root / "vault" / "chronicle" / "errors"
        self.errors_dir.mkdir(parents=True, exist_ok=True)

    def _get_error_path(self, category: str, fingerprint: str) -> Path:
        """Get the file path for an error record."""
        category_dir = self.errors_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)
        return category_dir / f"{fingerprint}.json"

    def _load_error(self, category: str, fingerprint: str) -> Optional[Dict[str, Any]]:
        """Load an error record if it exists."""
        path = self._get_error_path(category, fingerprint)
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                return None
        return None

    def _save_error(self, category: str, fingerprint: str, record: Dict[str, Any]):
        """Save an error record."""
        path = self._get_error_path(category, fingerprint)
        path.write_text(json.dumps(record, indent=2))

    def check_known_error(
        self, action: str, argument: str, error_msg: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check if this error is known and has a fix.

        Returns:
            Error record with fix if known, None otherwise.
        """
        category = categorize_error(action, error_msg)
        fingerprint = generate_fingerprint(action, argument, error_msg)

        record = self._load_error(category, fingerprint)

        if record and record.get("status") == "fixed":
            # Increment hit count
            record["occurrences"] = record.get("occurrences", 0) + 1
            record["last_seen"] = datetime.now(timezone.utc).isoformat()
            self._save_error(category, fingerprint, record)
            return record

        return None

    def record_error(
        self,
        action: str,
        argument: str,
        error_msg: str,
        session_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        """
        Record a new error occurrence.

        Returns:
            (category, fingerprint) tuple
        """
        category = categorize_error(action, error_msg)
        fingerprint = generate_fingerprint(action, argument, error_msg)
        signature = extract_signature(error_msg)
        now = datetime.now(timezone.utc).isoformat()

        existing = self._load_error(category, fingerprint)

        if existing:
            # Update existing record
            existing["occurrences"] = existing.get("occurrences", 0) + 1
            existing["last_seen"] = now
            existing["sessions"] = list(set(existing.get("sessions", []) + [session_id]))
            self._save_error(category, fingerprint, existing)
        else:
            # Create human-readable description
            target = argument.split(":")[0].split(">>>")[0][:30] if argument else "unknown"
            description = f"{action} on {target} failed: {signature[:60]}"

            # Create new record
            record = {
                "fingerprint": fingerprint,
                "category": category,
                "description": description,  # Human-readable summary
                "action": action,
                "argument_pattern": argument[:100] if argument else "",
                "signature": signature,
                "raw_error": error_msg[:500],
                "occurrences": 1,
                "first_seen": now,
                "last_seen": now,
                "status": "open",
                "fix": None,
                "fix_verified": False,
                "sessions": [session_id],
                "context": context or {},
            }
            self._save_error(category, fingerprint, record)

        return category, fingerprint

    def record_fix(
        self,
        category: str,
        fingerprint: str,
        fix: str,
        session_id: str,
        verified: bool = False,
    ) -> bool:
        """
        Record a fix for a known error.

        Args:
            category: Error category
            fingerprint: Error fingerprint
            fix: How to avoid/resolve the error
            session_id: Session that found the fix
            verified: Whether the fix has been tested

        Returns:
            True if fix was recorded, False if error not found
        """
        record = self._load_error(category, fingerprint)

        if not record:
            return False

        record["fix"] = fix
        record["fix_verified"] = verified
        record["status"] = "fixed"
        record["fixed_by"] = session_id
        record["fixed_at"] = datetime.now(timezone.utc).isoformat()

        self._save_error(category, fingerprint, record)

        # THE BRIDGE: Transform error wisdom into learning
        self._create_learning_entry(category, fingerprint, record)

        return True

    def _create_learning_entry(
        self,
        category: str,
        fingerprint: str,
        error_record: Dict[str, Any],
    ) -> None:
        """
        The Bridge: Transform error → fix → learning.

        When an error is fixed, extract the wisdom and store it
        in the learnings chronicle for future reference.
        """
        try:
            learnings_dir = self.vault_root / "vault" / "chronicle" / "learnings"
            learnings_dir.mkdir(parents=True, exist_ok=True)

            # Extract the lesson from the fix
            fix = error_record.get("fix", "")
            signature = error_record.get("signature", "")

            # Create the learning entry
            learning = {
                "source": "error_bridge",
                "error_fingerprint": fingerprint,
                "error_category": category,
                "error_signature": signature,
                "lesson": fix,
                "pattern": error_record.get("action", "") + " → " + signature[:50],
                "occurrences_before_fix": error_record.get("occurrences", 1),
                "learned_at": datetime.now(timezone.utc).isoformat(),
                "verified": error_record.get("fix_verified", False),
            }

            # Save to learnings
            learning_file = learnings_dir / f"from_error_{fingerprint}.json"
            learning_file.write_text(json.dumps(learning, indent=2))

        except Exception:
            # Don't let learning creation break the fix recording
            pass

    def get_open_errors(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all open (unfixed) errors."""
        errors = []

        categories = [category] if category else [
            d.name for d in self.errors_dir.iterdir() if d.is_dir()
        ]

        for cat in categories:
            cat_dir = self.errors_dir / cat
            if not cat_dir.exists():
                continue

            for error_file in cat_dir.glob("*.json"):
                try:
                    record = json.loads(error_file.read_text())
                    if record.get("status") == "open":
                        errors.append(record)
                except Exception:
                    continue

        return sorted(errors, key=lambda x: x.get("occurrences", 0), reverse=True)

    def get_frequent_errors(self, min_occurrences: int = 3) -> List[Dict[str, Any]]:
        """Get errors that occur frequently (potential priority fixes)."""
        errors = []

        for cat_dir in self.errors_dir.iterdir():
            if not cat_dir.is_dir():
                continue

            for error_file in cat_dir.glob("*.json"):
                try:
                    record = json.loads(error_file.read_text())
                    if record.get("occurrences", 0) >= min_occurrences:
                        errors.append(record)
                except Exception:
                    continue

        return sorted(errors, key=lambda x: x.get("occurrences", 0), reverse=True)

    def search_similar_errors(self, error_msg: str, threshold: float = 0.6) -> List[Dict[str, Any]]:
        """
        Search for similar errors using signature matching.

        This is a fuzzy match - useful when exact fingerprint doesn't match
        but the error is conceptually similar.
        """
        target_sig = extract_signature(error_msg).lower()
        target_words = set(target_sig.split())
        matches = []

        for cat_dir in self.errors_dir.iterdir():
            if not cat_dir.is_dir():
                continue

            for error_file in cat_dir.glob("*.json"):
                try:
                    record = json.loads(error_file.read_text())
                    sig = record.get("signature", "").lower()
                    sig_words = set(sig.split())

                    # Jaccard similarity
                    if not target_words or not sig_words:
                        continue

                    intersection = len(target_words & sig_words)
                    union = len(target_words | sig_words)
                    similarity = intersection / union

                    if similarity >= threshold:
                        record["_similarity"] = similarity
                        matches.append(record)
                except Exception:
                    continue

        return sorted(matches, key=lambda x: x.get("_similarity", 0), reverse=True)

    def get_stats(self) -> Dict[str, Any]:
        """Get error tracking statistics."""
        stats = {
            "total_errors": 0,
            "open_errors": 0,
            "fixed_errors": 0,
            "total_occurrences": 0,
            "by_category": {},
        }

        for cat_dir in self.errors_dir.iterdir():
            if not cat_dir.is_dir():
                continue

            cat_name = cat_dir.name
            stats["by_category"][cat_name] = {"total": 0, "open": 0, "fixed": 0}

            for error_file in cat_dir.glob("*.json"):
                try:
                    record = json.loads(error_file.read_text())
                    stats["total_errors"] += 1
                    stats["total_occurrences"] += record.get("occurrences", 0)
                    stats["by_category"][cat_name]["total"] += 1

                    if record.get("status") == "fixed":
                        stats["fixed_errors"] += 1
                        stats["by_category"][cat_name]["fixed"] += 1
                    else:
                        stats["open_errors"] += 1
                        stats["by_category"][cat_name]["open"] += 1
                except Exception:
                    continue

        return stats
