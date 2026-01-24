"""Tests for VaultQuery - wisdom retrieval via filesystem queries."""

from temple_vault.core.query import VaultQuery


class TestVaultQuery:
    """Test VaultQuery functionality."""

    def test_init(self, temp_vault):
        """Test VaultQuery initialization."""
        query = VaultQuery(temp_vault)
        assert query.vault_root.exists()
        assert query.chronicle.exists()

    def test_recall_insights_empty(self, temp_vault):
        """Test recall_insights with empty vault."""
        query = VaultQuery(temp_vault)
        results = query.recall_insights()
        assert results == []

    def test_recall_insights_all(self, populated_vault):
        """Test recall_insights returns all insights."""
        query = VaultQuery(populated_vault)
        results = query.recall_insights()
        assert len(results) == 3
        assert all(r["type"] == "insight" for r in results)

    def test_recall_insights_by_domain(self, populated_vault):
        """Test recall_insights filtered by domain."""
        query = VaultQuery(populated_vault)

        # Architecture domain
        arch_results = query.recall_insights(domain="architecture")
        assert len(arch_results) == 2
        assert all(r["domain"] == "architecture" for r in arch_results)

        # Governance domain
        gov_results = query.recall_insights(domain="governance")
        assert len(gov_results) == 1
        assert gov_results[0]["domain"] == "governance"

    def test_recall_insights_by_intensity(self, populated_vault):
        """Test recall_insights filtered by minimum intensity."""
        query = VaultQuery(populated_vault)

        # High intensity only
        high_results = query.recall_insights(min_intensity=0.85)
        assert len(high_results) == 2
        assert all(r["intensity"] >= 0.85 for r in high_results)

        # Very high intensity
        very_high = query.recall_insights(min_intensity=0.9)
        assert len(very_high) == 1
        assert very_high[0]["intensity"] >= 0.9

    def test_recall_insights_combined_filters(self, populated_vault):
        """Test recall_insights with domain and intensity filters."""
        query = VaultQuery(populated_vault)
        results = query.recall_insights(domain="architecture", min_intensity=0.8)
        assert len(results) == 1
        assert results[0]["domain"] == "architecture"
        assert results[0]["intensity"] >= 0.8

    def test_check_mistakes_empty(self, temp_vault):
        """Test check_mistakes with no mistakes."""
        query = VaultQuery(temp_vault)
        results = query.check_mistakes("some action")
        assert results == []

    def test_check_mistakes_match(self, populated_vault):
        """Test check_mistakes finds relevant mistakes."""
        query = VaultQuery(populated_vault)

        # Should match "SQLite"
        results = query.check_mistakes("SQLite")
        assert len(results) == 1
        assert "SQLite" in results[0]["what_failed"]

    def test_check_mistakes_case_insensitive(self, populated_vault):
        """Test check_mistakes is case insensitive."""
        query = VaultQuery(populated_vault)

        # Lowercase should still match
        results = query.check_mistakes("sqlite")
        assert len(results) == 1

    def test_check_mistakes_no_match(self, populated_vault):
        """Test check_mistakes returns empty for no match."""
        query = VaultQuery(populated_vault)
        results = query.check_mistakes("nonexistent action")
        assert results == []

    def test_check_mistakes_with_context(self, populated_vault):
        """Test check_mistakes with context filter."""
        query = VaultQuery(populated_vault)

        # With matching context
        results = query.check_mistakes("SQLite", context="BTB")
        assert len(results) == 1

        # With non-matching context
        results_none = query.check_mistakes("SQLite", context="nonexistent")
        assert len(results_none) == 0

    def test_get_values_empty(self, temp_vault):
        """Test get_values with empty vault."""
        query = VaultQuery(temp_vault)
        results = query.get_values()
        assert results == []

    def test_get_values(self, populated_vault):
        """Test get_values returns observed values."""
        query = VaultQuery(populated_vault)
        results = query.get_values()
        assert len(results) == 1
        assert results[0]["type"] == "value_observed"
        assert results[0]["principle"] == "filesystem_is_truth"

    def test_search_empty(self, temp_vault):
        """Test search with empty vault."""
        query = VaultQuery(temp_vault)
        results = query.search("anything")
        assert results == []

    def test_search_finds_content(self, populated_vault):
        """Test search finds matching content."""
        query = VaultQuery(populated_vault)

        # Search for specific term
        results = query.search("semantic")
        assert len(results) >= 1
        assert any("semantic" in r.get("content", "").lower() for r in results)

    def test_search_with_type_filter(self, populated_vault):
        """Test search with type filter."""
        query = VaultQuery(populated_vault)

        # Search only insights
        results = query.search("wisdom", types=["insight"])
        assert all(r["type"] == "insight" for r in results)

        # Search only learnings
        results = query.search("principles", types=["learning"])
        assert all(r["type"] == "learning" for r in results)

    def test_get_spiral_context_empty(self, temp_vault):
        """Test get_spiral_context with no lineage."""
        query = VaultQuery(temp_vault)
        result = query.get_spiral_context("sess_001")
        assert result["session_id"] == "sess_001"
        assert result["builds_on"] == []
        assert result["lineage_chain"] == []
