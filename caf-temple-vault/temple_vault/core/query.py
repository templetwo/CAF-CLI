"""Wisdom retrieval via filesystem queries (glob + grep + jq logic)."""

import glob
import json
from pathlib import Path
from typing import List, Dict, Any, Optional


class VaultQuery:
    """Query engine for Temple Vault using pure filesystem operations."""

    def __init__(self, vault_root: str):
        self.vault_root = Path(vault_root).expanduser()
        self.chronicle = self.vault_root / "vault" / "chronicle"
        self.global_path = self.vault_root / "global"

    def _load_jsonl(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load JSONL file into list of dicts (skips malformed lines)."""
        if not file_path.exists():
            return []
        results = []
        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    # Skip malformed lines
                    pass
        return results

    def recall_insights(
        self, domain: Optional[str] = None, min_intensity: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Query insights from vault/chronicle/insights/{domain}/*.jsonl

        Args:
            domain: Filter by domain (e.g., "governance", "demos"). None = all domains.
            min_intensity: Minimum intensity threshold (0.0-1.0)

        Returns:
            List of insight dicts matching criteria

        Implementation:
            glob: vault/chronicle/insights/{domain or *}/*.jsonl
            filter: jq 'select(.type == "insight" and .intensity >= min_intensity)'
        """
        pattern = self.chronicle / "insights" / (domain or "*") / "*.jsonl"
        files = glob.glob(str(pattern), recursive=True)

        results = []
        for file in files:
            entries = self._load_jsonl(Path(file))
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if entry.get("type") == "insight" and entry.get("intensity", 0) >= min_intensity:
                    results.append(entry)

        return results

    def check_mistakes(self, action: str, context: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Check for documented mistakes related to an action.

        Args:
            action: Action to check (e.g., "use nvidia-smi")
            context: Additional context filter (e.g., "jetson")

        Returns:
            List of learning dicts with mistake warnings

        Implementation:
            grep: vault/chronicle/learnings/mistakes/*.jsonl for action
            filter: if context provided, only return matches containing context

        Example:
            check_mistakes("use nvidia-smi", "jetson")
            → Returns: "Session 16: Jetson uses tegrastats, not nvidia-smi"
        """
        pattern = self.chronicle / "learnings" / "mistakes" / "*.jsonl"
        files = glob.glob(str(pattern), recursive=True)

        results = []
        for file in files:
            entries = self._load_jsonl(Path(file))
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if entry.get("type") != "learning":
                    continue

                # Check if action matches
                what_failed = entry.get("what_failed", "").lower()
                if action.lower() not in what_failed:
                    continue

                # If context provided, filter by it
                if context:
                    entry_context = json.dumps(entry).lower()
                    if context.lower() not in entry_context:
                        continue

                results.append(entry)

        return results

    def get_values(self) -> List[Dict[str, Any]]:
        """
        Get user values from vault/chronicle/values/principles/*.jsonl

        Returns:
            List of value/principle dicts

        Implementation:
            cat: vault/chronicle/values/principles/*.jsonl
        """
        pattern = self.chronicle / "values" / "principles" / "*.jsonl"
        files = glob.glob(str(pattern), recursive=True)

        results = []
        for file in files:
            entries = self._load_jsonl(Path(file))
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if entry.get("type") == "value_observed":
                    results.append(entry)

        return results

    def get_spiral_context(self, session_id: str) -> Dict[str, Any]:
        """
        Get session lineage context (what this session builds on).

        Args:
            session_id: Session ID to look up (e.g., "sess_123")

        Returns:
            Dict with:
                - builds_on: List of prior insight IDs
                - lineage_chain: Session progression
                - related_sessions: Sessions in the chain

        Implementation:
            Reads: vault/chronicle/lineage/*{session_id}*.jsonl
            Traverses: builds_on relationships recursively
        """
        pattern = self.chronicle / "lineage" / f"*{session_id}*.jsonl"
        files = glob.glob(str(pattern), recursive=True)

        builds_on = []
        lineage_chain = []

        for file in files:
            entries = self._load_jsonl(Path(file))
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if entry.get("type") == "lineage" and entry.get("session_id") == session_id:
                    builds_on.extend(entry.get("builds_on", []))
                    lineage_chain = entry.get("lineage_chain", [])

        # Extract session IDs from lineage chain
        related_sessions = [item.split("_")[1] if "_" in item else item for item in lineage_chain]

        return {
            "session_id": session_id,
            "builds_on": builds_on,
            "lineage_chain": lineage_chain,
            "related_sessions": list(set(related_sessions)),
        }

    def search(
        self,
        query: str,
        types: Optional[List[str]] = None,
        time_range: Optional[tuple] = None,
    ) -> List[Dict[str, Any]]:
        """
        General search across all chronicle files.

        Args:
            query: Search term
            types: Event types to filter (e.g., ["insight", "learning"])
            time_range: (start_ts, end_ts) tuple for filtering

        Returns:
            List of matching entries

        Implementation:
            grep: vault/chronicle/**/*.jsonl for query
            filter: by type and timestamp if provided
        """
        pattern = self.chronicle / "**" / "*.jsonl"
        files = glob.glob(str(pattern), recursive=True)

        results = []
        for file in files:
            entries = self._load_jsonl(Path(file))
            for entry in entries:
                if not isinstance(entry, dict):
                    continue

                # Text search
                entry_text = json.dumps(entry).lower()
                if query.lower() not in entry_text:
                    continue

                # Type filter
                if types and entry.get("type") not in types:
                    continue

                # Time range filter
                if time_range:
                    ts = entry.get("timestamp", "")
                    if not (time_range[0] <= ts <= time_range[1]):
                        continue

                results.append(entry)

        return results
