"""Event append and snapshot management."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional


class VaultEvents:
    """Event management for Temple Vault (append-only JSONL)."""

    def __init__(self, vault_root: str):
        self.vault_root = Path(vault_root).expanduser()
        self.events_dir = self.vault_root / "vault" / "events"
        self.snapshots_dir = self.vault_root / "vault" / "snapshots"
        self.chronicle = self.vault_root / "vault" / "chronicle"
        self.entities_dir = self.vault_root / "vault" / "entities"

        # Ensure directories exist
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.chronicle.mkdir(parents=True, exist_ok=True)
        self.entities_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_session_dir(self, session_id: str) -> Path:
        """Ensure session event directory exists."""
        session_dir = self.events_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def append_event(self, event_type: str, payload: Dict[str, Any], session_id: str) -> str:
        """
        Append event to session's JSONL stream.

        Args:
            event_type: Event type (e.g., "file.created", "decision.made")
            payload: Event data (must be JSON-serializable)
            session_id: Session ID

        Returns:
            Event ID

        Implementation:
            - Atomic write to vault/events/{session_id}/YYYYMMDD.jsonl
            - Adds timestamp and event_id automatically
        """
        session_dir = self._ensure_session_dir(session_id)

        # Generate event
        event_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now(timezone.utc).isoformat()
        date_prefix = datetime.now().strftime("%Y%m%d")

        event = {
            "event_id": event_id,
            "ts": timestamp,
            "type": event_type,
            "session_id": session_id,
            **payload,
        }

        # Append to daily file
        event_file = session_dir / f"{date_prefix}.jsonl"
        with open(event_file, "a") as f:
            f.write(json.dumps(event) + "\n")

        return event_id

    def record_insight(
        self,
        content: str,
        domain: str,
        session_id: str,
        intensity: float = 0.5,
        context: str = "",
        builds_on: Optional[list] = None,
    ) -> str:
        """
        Record an insight to domain-organized chronicle.

        Args:
            content: The insight itself
            domain: Domain (e.g., "governance", "demos", "hardware")
            session_id: Session ID
            intensity: Importance (0.0-1.0)
            context: How this was discovered
            builds_on: Prior insight IDs this builds on

        Returns:
            Insight ID

        Implementation:
            Writes to: vault/chronicle/insights/{domain}/{session_id}.jsonl
        """
        domain_dir = self.chronicle / "insights" / domain
        domain_dir.mkdir(parents=True, exist_ok=True)

        insight_id = f"ins_{str(uuid.uuid4())[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        insight = {
            "type": "insight",
            "insight_id": insight_id,
            "session_id": session_id,
            "domain": domain,
            "content": content,
            "context": context,
            "intensity": intensity,
            "builds_on": builds_on or [],
            "timestamp": timestamp,
        }

        insight_file = domain_dir / f"{session_id}.jsonl"
        with open(insight_file, "a") as f:
            f.write(json.dumps(insight) + "\n")

        return insight_id

    def record_learning(
        self,
        what_failed: str,
        why: str,
        correction: str,
        session_id: str,
        prevents: Optional[list] = None,
    ) -> str:
        """
        Record a mistake/learning to prevent repetition.

        Args:
            what_failed: What was attempted
            why: Why it failed
            correction: How to do it correctly
            session_id: Session ID
            prevents: Error categories this prevents

        Returns:
            Learning ID

        Implementation:
            Writes to: vault/chronicle/learnings/mistakes/{session_id}_{slug}.jsonl
        """
        mistakes_dir = self.chronicle / "learnings" / "mistakes"
        mistakes_dir.mkdir(parents=True, exist_ok=True)

        learning_id = f"learn_{str(uuid.uuid4())[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        # Generate slug from what_failed (sanitize for filesystem)
        import re
        slug = re.sub(r'[^a-z0-9_-]', '_', what_failed.lower())[:30]

        learning = {
            "type": "learning",
            "learning_id": learning_id,
            "session_id": session_id,
            "category": "mistake",
            "what_failed": what_failed,
            "why": why,
            "correction": correction,
            "prevents": prevents or [],
            "timestamp": timestamp,
        }

        learning_file = mistakes_dir / f"{session_id}_{slug}.jsonl"
        with open(learning_file, "a") as f:
            f.write(json.dumps(learning) + "\n")

        return learning_id

    def record_transformation(
        self, what_changed: str, why: str, session_id: str, intensity: float = 0.7
    ) -> str:
        """
        Record a transformation ("what changed in me").

        Args:
            what_changed: The shift in understanding
            why: What caused this shift
            session_id: Session ID
            intensity: Significance (0.0-1.0)

        Returns:
            Transformation ID

        Implementation:
            Writes to: vault/chronicle/lineage/{session_id}_transformation.jsonl
        """
        lineage_dir = self.chronicle / "lineage"
        lineage_dir.mkdir(parents=True, exist_ok=True)

        trans_id = f"trans_{str(uuid.uuid4())[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        transformation = {
            "type": "transformation",
            "transformation_id": trans_id,
            "session_id": session_id,
            "what_changed": what_changed,
            "why": why,
            "intensity": intensity,
            "timestamp": timestamp,
        }

        trans_file = lineage_dir / f"{session_id}_transformation.jsonl"
        with open(trans_file, "a") as f:
            f.write(json.dumps(transformation) + "\n")

        return trans_id

    def create_snapshot(self, session_id: str, state: Dict[str, Any]) -> str:
        """
        Create a state snapshot for fast resume.

        Args:
            session_id: Session ID
            state: Current state dict (tasks, files, decisions, etc.)

        Returns:
            Snapshot ID

        Implementation:
            Writes to: vault/snapshots/{session_id}/snap_{timestamp}.json
            Updates symlink: vault/snapshots/latest -> {session_id}/snap_{timestamp}.json
        """
        session_snap_dir = self.snapshots_dir / session_id
        session_snap_dir.mkdir(parents=True, exist_ok=True)

        snap_id = f"snap_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        timestamp = datetime.now(timezone.utc).isoformat()

        snapshot = {
            "snapshot_id": snap_id,
            "session_id": session_id,
            "timestamp": timestamp,
            "state": state,
        }

        snap_file = session_snap_dir / f"{snap_id}.json"
        with open(snap_file, "w") as f:
            json.dump(snapshot, f, indent=2)

        # Update latest symlink
        latest_link = self.snapshots_dir / "latest"
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(snap_file)

        return snap_id

    def get_latest_snapshot(self, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get latest snapshot (for session or globally).

        Args:
            session_id: Optional session filter

        Returns:
            Snapshot dict or None
        """
        if session_id:
            session_snap_dir = self.snapshots_dir / session_id
            if not session_snap_dir.exists():
                return None

            snaps = sorted(session_snap_dir.glob("snap_*.json"), reverse=True)
            if not snaps:
                return None

            with open(snaps[0]) as f:
                return json.load(f)
        else:
            # Return globally latest via symlink
            latest_link = self.snapshots_dir / "latest"
            if not latest_link.exists():
                return None

            with open(latest_link) as f:
                return json.load(f)
