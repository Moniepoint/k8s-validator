"""CRD detection from Kubernetes manifests."""

from typing import Any, Dict, Optional, Set

from k8s_validator.core.models import CRDInfo


# Built-in Kubernetes API groups (not CRDs)
BUILTIN_GROUPS: Set[str] = {
    "",  # core group
    "apps",
    "batch",
    "autoscaling",
    "policy",
    "networking.k8s.io",
    "rbac.authorization.k8s.io",
    "storage.k8s.io",
    "admissionregistration.k8s.io",
    "apiextensions.k8s.io",
    "scheduling.k8s.io",
    "coordination.k8s.io",
    "node.k8s.io",
    "discovery.k8s.io",
    "flowcontrol.apiserver.k8s.io",
    "internal.apiserver.k8s.io",
}


class CRDDetector:
    """Detects Custom Resource Definitions in manifests."""

    @staticmethod
    def is_crd(manifest: Dict[str, Any]) -> bool:
        """Check if manifest is a CRD instance."""
        api_version = manifest.get("apiVersion", "")

        # Must have a group (contains "/")
        if "/" not in api_version:
            return False

        group = api_version.split("/")[0]

        # Must not be a built-in group
        return group not in BUILTIN_GROUPS

    @staticmethod
    def detect(manifest: Dict[str, Any]) -> Optional[CRDInfo]:
        """Detect CRD information from manifest."""
        api_version = manifest.get("apiVersion")
        kind = manifest.get("kind")

        if not api_version or not kind:
            return None

        if "/" not in api_version:
            # Built-in resource
            return None

        group, version = api_version.split("/", 1)

        if group in BUILTIN_GROUPS:
            # Built-in resource
            return None

        # Derive plural name (simple pluralization)
        plural = CRDDetector._pluralize(kind)

        return CRDInfo(
            group=group,
            version=version,
            kind=kind,
            plural=plural,
            api_version=api_version,
        )

    @staticmethod
    def _pluralize(kind: str) -> str:
        """Simple English pluralization for CRD kinds."""
        kind_lower = kind.lower()

        # Special cases for common CRDs
        special_cases = {
            "virtualservice": "virtualservices",
            "destinationrule": "destinationrules",
            "gateway": "gateways",
            "serviceentry": "serviceentries",
            "application": "applications",
            "appproject": "appprojects",
            "applicationset": "applicationsets",
            "certificate": "certificates",
            "issuer": "issuers",
            "clusterissuer": "clusterissuers",
            "httproute": "httproutes",
            "tcproute": "tcproutes",
            "grpcroute": "grpcroutes",
            "workflow": "workflows",
            "cronworkflow": "cronworkflows",
            "rollout": "rollouts",
        }

        if kind_lower in special_cases:
            return special_cases[kind_lower]

        # General rules
        if kind_lower.endswith("s"):
            return kind_lower + "es"
        elif kind_lower.endswith("y") and kind_lower[-2] not in "aeiou":
            return kind_lower[:-1] + "ies"
        else:
            return kind_lower + "s"
