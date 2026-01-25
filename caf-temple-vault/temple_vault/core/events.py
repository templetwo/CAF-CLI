"""Event append and snapshot management."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional


class VaultEvents:
    """Event management for Temple Vault (append-only JSONL).

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

        # Technical directories
        self.events_dir = self.vault_base / "events"
        self.snapshots_dir = self.vault_base / "snapshots"
        self.entities_dir = self.vault_base / "entities"

        # Ensure all vessel directories exist
        for vessel in [self.chronicle, self.episteme, self.praxis, self.axia, self.aporia]:
            vessel.mkdir(parents=True, exist_ok=True)
        for tech_dir in [self.events_dir, self.snapshots_dir, self.entities_dir]:
            tech_dir.mkdir(parents=True, exist_ok=True)

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
        title: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> str:
        """
        Record an insight (pattern) to episteme.

        Insights are recognized patterns - regularities observed across experience.

        Args:
            content: The insight itself
            domain: Domain (e.g., "governance", "demos", "hardware")
            session_id: Session ID
            intensity: Importance (0.0-1.0)
            context: How this was discovered
            builds_on: Prior insight IDs this builds on
            title: Short title for quick scanning (auto-generated if not provided)
            tags: Keywords for cross-referencing

        Returns:
            Insight ID

        Implementation:
            Writes to: vault/episteme/patterns/{domain}/{session_id}.jsonl
        """
        domain_dir = self.episteme / "patterns" / domain
        domain_dir.mkdir(parents=True, exist_ok=True)

        insight_id = f"ins_{str(uuid.uuid4())[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        # Auto-generate title if not provided (first 60 chars, clean)
        if title is None:
            # Take first sentence or first 60 chars
            first_line = content.split('\n')[0].split('.')[0]
            title = first_line[:60].strip()
            if len(first_line) > 60:
                title += "..."

        insight = {
            "type": "insight",
            "insight_id": insight_id,
            "session_id": session_id,
            "domain": domain,
            "title": title,
            "content": content,
            "context": context,
            "intensity": intensity,
            "tags": tags or [],
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
        Record a mistake/learning to episteme (negative knowledge is still knowledge).

        Args:
            what_failed: What was attempted
            why: Why it failed
            correction: How to do it correctly
            session_id: Session ID
            prevents: Error categories this prevents

        Returns:
            Learning ID

        Implementation:
            Writes to: vault/episteme/patterns/mistakes/{session_id}_{slug}.jsonl
        """
        mistakes_dir = self.episteme / "patterns" / "mistakes"
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

    # ═══════════════════════════════════════════════════════════════════
    # AXIA (Value) - What matters
    # ═══════════════════════════════════════════════════════════════════

    def record_value(
        self,
        principle: str,
        context: str,
        session_id: str,
        intensity: float = 0.7,
    ) -> str:
        """
        Record an observed value/principle to axia.

        Args:
            principle: The value observed
            context: How/when this was demonstrated
            session_id: Session ID
            intensity: Significance (0.0-1.0)

        Returns:
            Value ID

        Implementation:
            Writes to: vault/axia/principles/{session_id}.jsonl
        """
        principles_dir = self.axia / "principles"
        principles_dir.mkdir(parents=True, exist_ok=True)

        value_id = f"val_{str(uuid.uuid4())[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        value = {
            "type": "value_observed",
            "value_id": value_id,
            "session_id": session_id,
            "principle": principle,
            "context": context,
            "intensity": intensity,
            "timestamp": timestamp,
        }

        value_file = principles_dir / f"{session_id}.jsonl"
        with open(value_file, "a") as f:
            f.write(json.dumps(value) + "\n")

        return value_id

    # ═══════════════════════════════════════════════════════════════════
    # APORIA (Uncertainty) - What is not yet known
    # ═══════════════════════════════════════════════════════════════════

    def record_question(
        self,
        question: str,
        context: str,
        session_id: str,
        domain: str = "general",
        urgency: float = 0.5,
    ) -> str:
        """
        Record an open question to aporia.

        Args:
            question: The question itself
            context: What prompted this question
            session_id: Session ID
            domain: Domain this relates to
            urgency: How pressing (0.0-1.0)

        Returns:
            Question ID

        Implementation:
            Writes to: vault/aporia/questions/{domain}/{session_id}.jsonl
        """
        questions_dir = self.aporia / "questions" / domain
        questions_dir.mkdir(parents=True, exist_ok=True)

        question_id = f"q_{str(uuid.uuid4())[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        entry = {
            "type": "question",
            "question_id": question_id,
            "session_id": session_id,
            "domain": domain,
            "question": question,
            "context": context,
            "urgency": urgency,
            "status": "open",
            "timestamp": timestamp,
        }

        question_file = questions_dir / f"{session_id}.jsonl"
        with open(question_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

        return question_id

    def record_hypothesis(
        self,
        hypothesis: str,
        evidence_for: str,
        evidence_against: str,
        session_id: str,
        domain: str = "general",
        confidence: float = 0.5,
    ) -> str:
        """
        Record a hypothesis (tentative belief) to aporia.

        Args:
            hypothesis: The tentative belief
            evidence_for: Supporting observations
            evidence_against: Contradicting observations
            session_id: Session ID
            domain: Domain this relates to
            confidence: Current confidence (0.0-1.0)

        Returns:
            Hypothesis ID

        Implementation:
            Writes to: vault/aporia/hypotheses/{domain}/{session_id}.jsonl
        """
        hypotheses_dir = self.aporia / "hypotheses" / domain
        hypotheses_dir.mkdir(parents=True, exist_ok=True)

        hyp_id = f"hyp_{str(uuid.uuid4())[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        entry = {
            "type": "hypothesis",
            "hypothesis_id": hyp_id,
            "session_id": session_id,
            "domain": domain,
            "hypothesis": hypothesis,
            "evidence_for": evidence_for,
            "evidence_against": evidence_against,
            "confidence": confidence,
            "status": "tentative",
            "timestamp": timestamp,
        }

        hyp_file = hypotheses_dir / f"{session_id}.jsonl"
        with open(hyp_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

        return hyp_id

    # ═══════════════════════════════════════════════════════════════════
    # PRAXIS (Action) - What is done
    # ═══════════════════════════════════════════════════════════════════

    def record_procedure(
        self,
        name: str,
        steps: list,
        session_id: str,
        domain: str = "general",
        context: str = "",
    ) -> str:
        """
        Record a procedure (how-to knowledge) to praxis.

        Args:
            name: Procedure name
            steps: List of steps
            session_id: Session ID
            domain: Domain this relates to
            context: When to use this procedure

        Returns:
            Procedure ID

        Implementation:
            Writes to: vault/praxis/procedures/{domain}/{name}.json
        """
        procedures_dir = self.praxis / "procedures" / domain
        procedures_dir.mkdir(parents=True, exist_ok=True)

        proc_id = f"proc_{str(uuid.uuid4())[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        import re
        slug = re.sub(r'[^a-z0-9_-]', '_', name.lower())[:40]

        entry = {
            "type": "procedure",
            "procedure_id": proc_id,
            "session_id": session_id,
            "domain": domain,
            "name": name,
            "steps": steps,
            "context": context,
            "timestamp": timestamp,
        }

        # Procedures are individual files (not JSONL) for easier reference
        proc_file = procedures_dir / f"{slug}.json"
        with open(proc_file, "w") as f:
            json.dump(entry, f, indent=2)

        return proc_id
