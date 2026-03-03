"""CRD schema loading from multiple sources."""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml

from k8s_validator.core.models import CRDInfo
from k8s_validator.crds.cache import CRDSchemaCache


class CRDSchemaLoader:
    """Loads CRD schemas from multiple sources."""

    # Datree CRD catalog base URL
    DATREE_CATALOG_URL = "https://raw.githubusercontent.com/datreeio/CRDs-catalog/main"

    def __init__(self, cache: Optional[CRDSchemaCache] = None) -> None:
        """Initialize schema loader."""
        self.cache = cache or CRDSchemaCache()

    def load_schema(
        self,
        crd_info: CRDInfo,
        sources: List[str],
        local_paths: Optional[List[Path]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Load CRD schema from available sources in priority order."""
        # Check cache first
        cache_key = f"{crd_info.group}/{crd_info.kind}/{crd_info.version}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        # Try each source in order
        for source in sources:
            schema = None

            if source == "cluster":
                schema = self._load_from_cluster(crd_info)
            elif source == "catalog":
                schema = self._load_from_catalog(crd_info)
            elif source == "local" and local_paths:
                schema = self._load_from_local(crd_info, local_paths)
            elif source == "embedded":
                schema = self._load_embedded(crd_info)

            if schema:
                # Cache successful load
                self.cache.set(cache_key, schema)
                return schema

        return None

    def _load_from_cluster(self, crd_info: CRDInfo) -> Optional[Dict[str, Any]]:
        """Load CRD schema from Kubernetes cluster via kubectl."""
        try:
            # Try to get CRD definition from cluster
            result = subprocess.run(
                ["kubectl", "get", "crd", crd_info.full_name, "-o", "json"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return None

            crd_def = json.loads(result.stdout)

            # Extract OpenAPIV3Schema from the CRD
            for version_spec in crd_def.get("spec", {}).get("versions", []):
                if version_spec.get("name") == crd_info.version:
                    return version_spec.get("schema", {}).get("openAPIV3Schema")

            return None

        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            return None

    def _load_from_catalog(self, crd_info: CRDInfo) -> Optional[Dict[str, Any]]:
        """Load CRD schema from Datree catalog."""
        # Try different URL formats
        urls = [
            f"{self.DATREE_CATALOG_URL}/{crd_info.group}/{crd_info.kind}_{crd_info.version}.json",
            f"{self.DATREE_CATALOG_URL}/{crd_info.group}/{crd_info.plural}_{crd_info.version}.json",
        ]

        for url in urls:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    return response.json()
            except requests.RequestException:
                continue

        return None

    def _load_from_local(
        self,
        crd_info: CRDInfo,
        search_paths: List[Path],
    ) -> Optional[Dict[str, Any]]:
        """Load CRD schema from local files."""
        for search_path in search_paths:
            if not search_path.exists():
                continue

            # Look for CRD files matching the group/kind
            patterns = [
                f"{crd_info.group}/*.yaml",
                f"{crd_info.group}/*.yml",
                f"*/{crd_info.kind.lower()}.yaml",
                f"*/{crd_info.kind.lower()}.yml",
            ]

            for pattern in patterns:
                for crd_file in search_path.glob(pattern):
                    schema = self._extract_schema_from_crd_file(crd_file, crd_info)
                    if schema:
                        return schema

        return None

    def _extract_schema_from_crd_file(
        self,
        crd_file: Path,
        crd_info: CRDInfo,
    ) -> Optional[Dict[str, Any]]:
        """Extract OpenAPIV3Schema from a CRD YAML file."""
        try:
            with open(crd_file) as f:
                crd_def = yaml.safe_load(f)

            if not isinstance(crd_def, dict):
                return None

            # Extract schema for the matching version
            for version_spec in crd_def.get("spec", {}).get("versions", []):
                if version_spec.get("name") == crd_info.version:
                    return version_spec.get("schema", {}).get("openAPIV3Schema")

            return None

        except Exception:
            return None

    def _load_embedded(self, crd_info: CRDInfo) -> Optional[Dict[str, Any]]:
        """Load from embedded schemas (for popular CRDs)."""
        # TODO: Implement embedded schemas for popular CRDs
        # For now, return None - this would be populated with pre-packaged schemas
        return None
