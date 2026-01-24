"""Tests for VaultEvents - event append and snapshot management."""

import json

from temple_vault.core.events import VaultEvents


class TestVaultEvents:
    """Test VaultEvents functionality."""

    def test_init_creates_directories(self, temp_vault):
        """Test VaultEvents creates required directories."""
        events = VaultEvents(temp_vault)
        assert events.events_dir.exists()
        assert events.snapshots_dir.exists()
        assert events.chronicle.exists()
        assert events.entities_dir.exists()

    def test_append_event(self, temp_vault):
        """Test appending an event to the stream."""
        events = VaultEvents(temp_vault)
        event_id = events.append_event(
            event_type="file.created",
            payload={"path": "/test/file.txt", "size": 100},
            session_id="sess_test",
        )

        assert event_id is not None
        assert len(event_id) == 8

        # Verify file was created
        session_dir = events.events_dir / "sess_test"
        assert session_dir.exists()
        event_files = list(session_dir.glob("*.jsonl"))
        assert len(event_files) == 1

        # Verify content
        with open(event_files[0]) as f:
            line = f.readline()
            event = json.loads(line)
            assert event["event_id"] == event_id
            assert event["type"] == "file.created"
            assert event["session_id"] == "sess_test"
            assert event["path"] == "/test/file.txt"

    def test_record_insight(self, temp_vault):
        """Test recording an insight."""
        events = VaultEvents(temp_vault)
        insight_id = events.record_insight(
            content="Test insight content",
            domain="architecture",
            session_id="sess_test",
            intensity=0.85,
            context="Testing",
            builds_on=["ins_prior"],
        )

        assert insight_id.startswith("ins_")

        # Verify file
        insight_file = events.chronicle / "insights" / "architecture" / "sess_test.jsonl"
        assert insight_file.exists()

        with open(insight_file) as f:
            insight = json.loads(f.readline())
            assert insight["type"] == "insight"
            assert insight["insight_id"] == insight_id
            assert insight["content"] == "Test insight content"
            assert insight["domain"] == "architecture"
            assert insight["intensity"] == 0.85
            assert insight["builds_on"] == ["ins_prior"]

    def test_record_insight_creates_domain_dir(self, temp_vault):
        """Test that recording insight creates domain directory."""
        events = VaultEvents(temp_vault)
        events.record_insight(
            content="New domain insight", domain="new_domain", session_id="sess_test"
        )

        domain_dir = events.chronicle / "insights" / "new_domain"
        assert domain_dir.exists()

    def test_record_learning(self, temp_vault):
        """Test recording a learning/mistake."""
        events = VaultEvents(temp_vault)
        learning_id = events.record_learning(
            what_failed="Used wrong command",
            why="Misunderstood the API",
            correction="Use the correct command",
            session_id="sess_test",
            prevents=["api_confusion"],
        )

        assert learning_id.startswith("learn_")

        # Verify file exists in mistakes directory
        mistakes_dir = events.chronicle / "learnings" / "mistakes"
        assert mistakes_dir.exists()
        mistake_files = list(mistakes_dir.glob("sess_test_*.jsonl"))
        assert len(mistake_files) == 1

        with open(mistake_files[0]) as f:
            learning = json.loads(f.readline())
            assert learning["type"] == "learning"
            assert learning["learning_id"] == learning_id
            assert learning["what_failed"] == "Used wrong command"
            assert learning["prevents"] == ["api_confusion"]

    def test_record_transformation(self, temp_vault):
        """Test recording a transformation."""
        events = VaultEvents(temp_vault)
        trans_id = events.record_transformation(
            what_changed="Now I understand the pattern",
            why="Working through the problem",
            session_id="sess_test",
            intensity=0.9,
        )

        assert trans_id.startswith("trans_")

        # Verify file
        trans_file = events.chronicle / "lineage" / "sess_test_transformation.jsonl"
        assert trans_file.exists()

        with open(trans_file) as f:
            trans = json.loads(f.readline())
            assert trans["type"] == "transformation"
            assert trans["transformation_id"] == trans_id
            assert trans["what_changed"] == "Now I understand the pattern"
            assert trans["intensity"] == 0.9

    def test_create_snapshot(self, temp_vault):
        """Test creating a state snapshot."""
        events = VaultEvents(temp_vault)
        snap_id = events.create_snapshot(
            session_id="sess_test", state={"tasks": ["task1", "task2"], "files": ["/a.txt"]}
        )

        assert snap_id.startswith("snap_")

        # Verify snapshot directory
        snap_dir = events.snapshots_dir / "sess_test"
        assert snap_dir.exists()

        # Verify latest symlink
        latest_link = events.snapshots_dir / "latest"
        assert latest_link.is_symlink()

    def test_get_latest_snapshot_none(self, temp_vault):
        """Test get_latest_snapshot when no snapshots exist."""
        events = VaultEvents(temp_vault)
        result = events.get_latest_snapshot()
        assert result is None

        result_session = events.get_latest_snapshot("sess_test")
        assert result_session is None

    def test_get_latest_snapshot_by_session(self, temp_vault):
        """Test get_latest_snapshot for specific session."""
        events = VaultEvents(temp_vault)

        # Create snapshots for different sessions
        events.create_snapshot("sess_001", {"data": "first"})
        events.create_snapshot("sess_002", {"data": "second"})

        # Get specific session
        result = events.get_latest_snapshot("sess_001")
        assert result is not None
        assert result["session_id"] == "sess_001"
        assert result["state"]["data"] == "first"

    def test_multiple_events_same_session(self, temp_vault):
        """Test appending multiple events to same session."""
        events = VaultEvents(temp_vault)

        id1 = events.append_event("event.one", {"n": 1}, "sess_test")
        id2 = events.append_event("event.two", {"n": 2}, "sess_test")
        id3 = events.append_event("event.three", {"n": 3}, "sess_test")

        assert id1 != id2 != id3

        # All events in same file
        session_dir = events.events_dir / "sess_test"
        event_files = list(session_dir.glob("*.jsonl"))
        assert len(event_files) == 1

        with open(event_files[0]) as f:
            lines = f.readlines()
            assert len(lines) == 3
