"""Wisdom retrieval via filesystem queries (glob + grep + jq logic)."""

import glob
import json
from pathlib import Path
from typing import List, Dict, Any, Optional


class VaultQuery:
    """Query engine for Temple Vault using pure filesystem operations.

    Philosophical Taxonomy (Five Vessels):
        chronicle/  - TEMPORAL: What happened (sessions, events, lineage)
        episteme/   - KNOWLEDGE: What is understood (patterns, facts, models, errors)
        praxis/     - ACTION: What is done (procedures, experiments, artifacts)
        axia/       - VALUE: What matters (principles, intentions, judgments)
        aporia/     - UNCERTAINTY: What is not yet known (questions, hypotheses, anomalies)
    """

    def __init__(self, vault_root: str):
        self.vault_root = Path(vault_root).expanduser()
        self.vault_base = self.vault_root / "vault"

        # The Five Vessels
        self.chronicle = self.vault_base / "chronicle"   # Temporal
        self.episteme = self.vault_base / "episteme"     # Knowledge
        self.praxis = self.vault_base / "praxis"         # Action
        self.axia = self.vault_base / "axia"             # Value
        self.aporia = self.vault_base / "aporia"         # Uncertainty

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
        self, domain: Optional[str] = None, min_intensity: float = 0.0,
        tags: Optional[List[str]] = None, limit: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Query insights (patterns) from episteme.

        Args:
            domain: Filter by domain (e.g., "governance", "demos"). None = all domains.
            min_intensity: Minimum intensity threshold (0.0-1.0)
            tags: Filter by tags (any match)
            limit: Max results (0 = unlimited)

        Returns:
            List of insight dicts matching criteria, sorted by timestamp desc

        Implementation:
            glob: vault/episteme/patterns/{domain or *}/*.jsonl
            filter: jq 'select(.type == "insight" and .intensity >= min_intensity)'
        """
        pattern = self.episteme / "patterns" / (domain or "*") / "*.jsonl"
        files = glob.glob(str(pattern), recursive=True)

        results = []
        for file in files:
            entries = self._load_jsonl(Path(file))
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if entry.get("type") != "insight":
                    continue
                if entry.get("intensity", 0) < min_intensity:
                    continue
                # Tag filter (any match)
                if tags:
                    entry_tags = entry.get("tags", [])
                    if not any(t in entry_tags for t in tags):
                        continue
                results.append(entry)

        # Sort by timestamp descending (newest first)
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        if limit > 0:
            results = results[:limit]

        return results

    def list_insight_titles(
        self, domain: Optional[str] = None, min_intensity: float = 0.0, limit: int = 20
    ) -> List[Dict[str, str]]:
        """
        Quick-scan: get just titles and IDs of insights.

        Args:
            domain: Filter by domain
            min_intensity: Minimum intensity
            limit: Max results

        Returns:
            List of {insight_id, title, domain, intensity, timestamp}
        """
        insights = self.recall_insights(domain, min_intensity, limit=limit)
        return [
            {
                "insight_id": i.get("insight_id", ""),
                "title": i.get("title", i.get("content", "")[:50]),
                "domain": i.get("domain", ""),
                "intensity": i.get("intensity", 0),
                "timestamp": i.get("timestamp", "")[:10],  # Just date
            }
            for i in insights
        ]

    def find_related(self, insight_id: str) -> List[Dict[str, Any]]:
        """
        Find insights related to a given insight via builds_on chain and shared tags.

        Args:
            insight_id: The insight to find relations for

        Returns:
            List of related insights (builds_on + tag matches)
        """
        # First, find the source insight
        all_insights = self.recall_insights()
        source = None
        for ins in all_insights:
            if ins.get("insight_id") == insight_id:
                source = ins
                break

        if not source:
            return []

        related = []
        source_tags = set(source.get("tags", []))
        builds_on = set(source.get("builds_on", []))

        for ins in all_insights:
            if ins.get("insight_id") == insight_id:
                continue  # Skip self

            # Check if this insight is in our builds_on
            if ins.get("insight_id") in builds_on:
                ins["_relation"] = "builds_on"
                related.append(ins)
                continue

            # Check if this insight builds on us
            if insight_id in ins.get("builds_on", []):
                ins["_relation"] = "built_by"
                related.append(ins)
                continue

            # Check for shared tags
            ins_tags = set(ins.get("tags", []))
            shared = source_tags & ins_tags
            if shared:
                ins["_relation"] = f"shared_tags:{','.join(shared)}"
                related.append(ins)

        return related

    def check_mistakes(self, action: str, context: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Check for documented mistakes related to an action.

        Args:
            action: Action to check (e.g., "use nvidia-smi")
            context: Additional context filter (e.g., "jetson")

        Returns:
            List of learning dicts with mistake warnings

        Implementation:
            grep: vault/episteme/patterns/mistakes/*.jsonl for action
            filter: if context provided, only return matches containing context

        Example:
            check_mistakes("use nvidia-smi", "jetson")
            → Returns: "Session 16: Jetson uses tegrastats, not nvidia-smi"
        """
        pattern = self.episteme / "patterns" / "mistakes" / "*.jsonl"
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
        Get user values from axia (the vessel of value).

        Returns:
            List of value/principle dicts

        Implementation:
            cat: vault/axia/principles/*.jsonl
        """
        pattern = self.axia / "principles" / "*.jsonl"
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
        vessels: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        General search across all vessels.

        Args:
            query: Search term
            types: Event types to filter (e.g., ["insight", "learning"])
            time_range: (start_ts, end_ts) tuple for filtering
            vessels: Which vessels to search (default: all five)
                     Options: ["chronicle", "episteme", "praxis", "axia", "aporia"]

        Returns:
            List of matching entries

        Implementation:
            grep: vault/{vessel}/**/*.jsonl for query
            filter: by type and timestamp if provided
        """
        # Default to all vessels
        vessel_paths = {
            "chronicle": self.chronicle,
            "episteme": self.episteme,
            "praxis": self.praxis,
            "axia": self.axia,
            "aporia": self.aporia,
        }

        if vessels:
            search_paths = [vessel_paths[v] for v in vessels if v in vessel_paths]
        else:
            search_paths = list(vessel_paths.values())

        files = []
        for vessel_path in search_paths:
            pattern = vessel_path / "**" / "*.jsonl"
            files.extend(glob.glob(str(pattern), recursive=True))

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

    # ═══════════════════════════════════════════════════════════════════
    # APORIA (Uncertainty) Queries
    # ═══════════════════════════════════════════════════════════════════

    def get_open_questions(
        self, domain: Optional[str] = None, min_urgency: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Get open questions from aporia.

        Args:
            domain: Filter by domain
            min_urgency: Minimum urgency threshold

        Returns:
            List of question dicts with status='open'
        """
        pattern = self.aporia / "questions" / (domain or "*") / "*.jsonl"
        files = glob.glob(str(pattern), recursive=True)

        results = []
        for file in files:
            entries = self._load_jsonl(Path(file))
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if entry.get("type") != "question":
                    continue
                if entry.get("status") != "open":
                    continue
                if entry.get("urgency", 0) < min_urgency:
                    continue
                results.append(entry)

        results.sort(key=lambda x: x.get("urgency", 0), reverse=True)
        return results

    def get_hypotheses(
        self, domain: Optional[str] = None, min_confidence: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Get hypotheses from aporia.

        Args:
            domain: Filter by domain
            min_confidence: Minimum confidence threshold

        Returns:
            List of hypothesis dicts
        """
        pattern = self.aporia / "hypotheses" / (domain or "*") / "*.jsonl"
        files = glob.glob(str(pattern), recursive=True)

        results = []
        for file in files:
            entries = self._load_jsonl(Path(file))
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if entry.get("type") != "hypothesis":
                    continue
                if entry.get("confidence", 0) < min_confidence:
                    continue
                results.append(entry)

        results.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return results

    # ═══════════════════════════════════════════════════════════════════
    # PRAXIS (Action) Queries
    # ═══════════════════════════════════════════════════════════════════

    def get_procedures(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get procedures from praxis.

        Args:
            domain: Filter by domain

        Returns:
            List of procedure dicts
        """
        pattern = self.praxis / "procedures" / (domain or "*") / "*.json"
        files = glob.glob(str(pattern), recursive=True)

        results = []
        for file in files:
            try:
                with open(file) as f:
                    entry = json.load(f)
                    if isinstance(entry, dict) and entry.get("type") == "procedure":
                        results.append(entry)
            except (json.JSONDecodeError, IOError):
                continue

        return results
