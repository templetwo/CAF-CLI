"""Cache builder - reconstructible inverted index from filesystem scan."""

import glob
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Any


class CacheBuilder:
    """Build reconstructible cache from filesystem."""

    def __init__(self, vault_root: str):
        self.vault_root = Path(vault_root).expanduser()
        self.cache_dir = self.vault_root / "vault" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_jsonl(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load JSONL file."""
        if not file_path.exists():
            return []
        with open(file_path, "r") as f:
            return [json.loads(line) for line in f if line.strip()]

    def _extract_keywords(self, text: str, min_length: int = 4) -> set:
        """Extract keywords from text (simple word split + filter)."""
        words = text.lower().split()
        return {w for w in words if len(w) >= min_length and w.isalpha()}

    def rebuild_cache(self) -> Dict[str, Any]:
        """
        Rebuild cache by scanning all JSONL files in vault.

        Returns:
            Stats dict with counts

        Writes:
            - vault/cache/inverted_index.json (term → files)
            - vault/cache/session_map.json (session_id → all files)
            - vault/cache/domain_map.json (domain → insight files)
        """
        # Initialize indexes
        inverted_index = defaultdict(lambda: {"files": set(), "frequency": 0})
        session_map = defaultdict(set)
        domain_map = defaultdict(set)

        # Scan all JSONL files
        pattern = str(self.vault_root / "vault" / "**" / "*.jsonl")
        files = glob.glob(pattern, recursive=True)

        total_entries = 0

        for file_path_str in files:
            file_path = Path(file_path_str)
            entries = self._load_jsonl(file_path)

            for entry in entries:
                total_entries += 1

                # Extract session ID
                session_id = entry.get("session_id")
                if session_id:
                    session_map[session_id].add(str(file_path))

                # Extract domain (for insights)
                if entry.get("type") == "insight":
                    domain = entry.get("domain")
                    if domain:
                        domain_map[domain].add(str(file_path))

                # Extract keywords from content
                content = entry.get("content", "")
                keywords = self._extract_keywords(content)

                for keyword in keywords:
                    inverted_index[keyword]["files"].add(str(file_path))
                    inverted_index[keyword]["frequency"] += 1

        # Convert sets to lists for JSON serialization
        inverted_index_json = {
            term: {"files": sorted(list(data["files"])), "frequency": data["frequency"]}
            for term, data in inverted_index.items()
        }

        session_map_json = {session: sorted(list(files)) for session, files in session_map.items()}

        domain_map_json = {domain: sorted(list(files)) for domain, files in domain_map.items()}

        # Write cache files
        with open(self.cache_dir / "inverted_index.json", "w") as f:
            json.dump(inverted_index_json, f, indent=2)

        with open(self.cache_dir / "session_map.json", "w") as f:
            json.dump(session_map_json, f, indent=2)

        with open(self.cache_dir / "domain_map.json", "w") as f:
            json.dump(domain_map_json, f, indent=2)

        return {
            "files_scanned": len(files),
            "total_entries": total_entries,
            "unique_keywords": len(inverted_index),
            "sessions_indexed": len(session_map),
            "domains_indexed": len(domain_map),
        }

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        inverted_path = self.cache_dir / "inverted_index.json"
        session_path = self.cache_dir / "session_map.json"
        domain_path = self.cache_dir / "domain_map.json"

        if not inverted_path.exists():
            return {"status": "no_cache", "message": "Run rebuild_cache() first"}

        with open(inverted_path) as f:
            inverted = json.load(f)
        with open(session_path) as f:
            sessions = json.load(f)
        with open(domain_path) as f:
            domains = json.load(f)

        return {
            "status": "cached",
            "unique_keywords": len(inverted),
            "sessions_indexed": len(sessions),
            "domains_indexed": len(domains),
        }

    def search_cache(self, keyword: str) -> List[str]:
        """
        Search cache for keyword (fast O(1) lookup).

        Args:
            keyword: Search term

        Returns:
            List of file paths containing keyword

        Fallback:
            If cache doesn't exist, returns empty list (caller should rebuild)
        """
        inverted_path = self.cache_dir / "inverted_index.json"
        if not inverted_path.exists():
            return []

        with open(inverted_path) as f:
            index = json.load(f)

        return index.get(keyword.lower(), {}).get("files", [])
