"""Tests for CacheBuilder - reconstructible inverted index."""

import json

from temple_vault.core.cache import CacheBuilder


class TestCacheBuilder:
    """Test CacheBuilder functionality."""

    def test_init_creates_cache_dir(self, temp_vault):
        """Test CacheBuilder creates cache directory."""
        cache = CacheBuilder(temp_vault)
        assert cache.cache_dir.exists()

    def test_get_cache_stats_no_cache(self, temp_vault):
        """Test get_cache_stats when no cache exists."""
        cache = CacheBuilder(temp_vault)
        stats = cache.get_cache_stats()
        assert stats["status"] == "no_cache"

    def test_rebuild_cache_empty(self, temp_vault):
        """Test rebuild_cache on empty vault."""
        cache = CacheBuilder(temp_vault)
        stats = cache.rebuild_cache()

        assert stats["files_scanned"] == 0
        assert stats["total_entries"] == 0
        assert stats["unique_keywords"] == 0

    def test_rebuild_cache_with_data(self, populated_vault):
        """Test rebuild_cache with populated vault."""
        cache = CacheBuilder(populated_vault)
        stats = cache.rebuild_cache()

        assert stats["files_scanned"] > 0
        assert stats["total_entries"] > 0
        assert stats["sessions_indexed"] > 0
        assert stats["domains_indexed"] > 0

    def test_cache_files_created(self, populated_vault):
        """Test that rebuild_cache creates all cache files."""
        cache = CacheBuilder(populated_vault)
        cache.rebuild_cache()

        assert (cache.cache_dir / "inverted_index.json").exists()
        assert (cache.cache_dir / "session_map.json").exists()
        assert (cache.cache_dir / "domain_map.json").exists()

    def test_get_cache_stats_after_rebuild(self, populated_vault):
        """Test get_cache_stats after rebuild."""
        cache = CacheBuilder(populated_vault)
        cache.rebuild_cache()
        stats = cache.get_cache_stats()

        assert stats["status"] == "cached"
        assert stats["unique_keywords"] > 0
        assert stats["sessions_indexed"] > 0
        assert stats["domains_indexed"] > 0

    def test_search_cache_no_cache(self, temp_vault):
        """Test search_cache when no cache exists."""
        cache = CacheBuilder(temp_vault)
        results = cache.search_cache("anything")
        assert results == []

    def test_search_cache_finds_keyword(self, populated_vault):
        """Test search_cache finds indexed keywords."""
        cache = CacheBuilder(populated_vault)
        cache.rebuild_cache()

        # Search for word in insights
        results = cache.search_cache("domain")
        assert len(results) > 0
        assert all(isinstance(r, str) for r in results)

    def test_search_cache_case_insensitive(self, populated_vault):
        """Test search_cache is case insensitive."""
        cache = CacheBuilder(populated_vault)
        cache.rebuild_cache()

        lower_results = cache.search_cache("semantic")
        upper_results = cache.search_cache("SEMANTIC")

        assert lower_results == upper_results

    def test_search_cache_no_match(self, populated_vault):
        """Test search_cache returns empty for no match."""
        cache = CacheBuilder(populated_vault)
        cache.rebuild_cache()

        results = cache.search_cache("xyznonexistentkeyword")
        assert results == []

    def test_domain_map_contents(self, populated_vault):
        """Test domain_map contains correct mappings."""
        cache = CacheBuilder(populated_vault)
        cache.rebuild_cache()

        with open(cache.cache_dir / "domain_map.json") as f:
            domain_map = json.load(f)

        assert "architecture" in domain_map
        assert "governance" in domain_map
        assert len(domain_map["architecture"]) >= 1

    def test_session_map_contents(self, populated_vault):
        """Test session_map contains correct mappings."""
        cache = CacheBuilder(populated_vault)
        cache.rebuild_cache()

        with open(cache.cache_dir / "session_map.json") as f:
            session_map = json.load(f)

        assert "sess_001" in session_map
        assert len(session_map["sess_001"]) >= 1

    def test_inverted_index_structure(self, populated_vault):
        """Test inverted_index has correct structure."""
        cache = CacheBuilder(populated_vault)
        cache.rebuild_cache()

        with open(cache.cache_dir / "inverted_index.json") as f:
            index = json.load(f)

        # Check structure of entries
        for keyword, data in index.items():
            assert "files" in data
            assert "frequency" in data
            assert isinstance(data["files"], list)
            assert isinstance(data["frequency"], int)
            assert data["frequency"] > 0

    def test_extract_keywords(self, temp_vault):
        """Test keyword extraction logic."""
        cache = CacheBuilder(temp_vault)

        keywords = cache._extract_keywords("This is a TEST with some LONG words")
        assert "this" in keywords
        assert "test" in keywords
        assert "with" in keywords
        assert "some" in keywords
        assert "long" in keywords
        assert "words" in keywords
        # Short words excluded
        assert "is" not in keywords
        assert "a" not in keywords

    def test_extract_keywords_min_length(self, temp_vault):
        """Test keyword extraction respects min_length."""
        cache = CacheBuilder(temp_vault)

        keywords = cache._extract_keywords("ab cd efgh ijklm", min_length=4)
        assert "efgh" in keywords
        assert "ijklm" in keywords
        assert "ab" not in keywords
        assert "cd" not in keywords

    def test_cache_is_reconstructible(self, populated_vault):
        """Test cache can be rebuilt from scratch."""
        cache = CacheBuilder(populated_vault)

        # Build once
        stats1 = cache.rebuild_cache()

        # Delete cache files
        for f in cache.cache_dir.glob("*.json"):
            f.unlink()

        # Rebuild
        stats2 = cache.rebuild_cache()

        # Should produce same results
        assert stats1 == stats2
