"""Platform auto-detection."""

from typing import Optional

from k8s_validator.platforms.base import PlatformAdapter
from k8s_validator.platforms.gitlab import GitLabAdapter
from k8s_validator.platforms.github import GitHubAdapter
from k8s_validator.platforms.harness import HarnessAdapter


def detect_platform() -> Optional[PlatformAdapter]:
    """Auto-detect which CI/CD platform is running."""
    platforms = [GitLabAdapter, GitHubAdapter, HarnessAdapter]

    for platform_class in platforms:
        if platform_class.detect():
            return platform_class()

    return None


def get_platform(platform_name: Optional[str] = None) -> Optional[PlatformAdapter]:
    """Get platform adapter by name or auto-detect."""
    if platform_name:
        platform_map = {
            "gitlab": GitLabAdapter,
            "github": GitHubAdapter,
            "harness": HarnessAdapter,
        }
        platform_class = platform_map.get(platform_name.lower())
        if platform_class:
            return platform_class()
        return None

    return detect_platform()
