"""CRD schema caching."""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional


class CRDSchemaCache:
    """Cache for CRD schemas."""

    # Cache TTL in seconds (24 hours)
    TTL = 24 * 60 * 60

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        """Initialize cache."""
        if cache_dir is None:
            cache_dir = Path.home() / ".k8s-validator" / "cache"

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get schema from cache."""
        cache_file = self._get_cache_file(key)

        if not cache_file.exists():
            return None

        # Check if expired
        if time.time() - cache_file.stat().st_mtime > self.TTL:
            cache_file.unlink()
            return None

        try:
            with open(cache_file) as f:
                return json.load(f)
        except Exception:
            return None

    def set(self, key: str, schema: Dict[str, Any]) -> None:
        """Store schema in cache."""
        cache_file = self._get_cache_file(key)

        try:
            with open(cache_file, "w") as f:
                json.dump(schema, f, indent=2)
        except Exception:
            pass  # Ignore cache write errors

    def _get_cache_file(self, key: str) -> Path:
        """Get cache file path for key."""
        # Sanitize key for filesystem
        safe_key = key.replace("/", "_").replace(":", "_")
        return self.cache_dir / f"{safe_key}.json"

    def clear(self) -> None:
        """Clear all cached schemas."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
