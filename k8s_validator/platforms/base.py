"""Base platform adapter interface."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from k8s_validator.core.models import ValidationResult


class PlatformAdapter(ABC):
    """Abstract base class for platform integrations."""

    @classmethod
    @abstractmethod
    def detect(cls) -> bool:
        """Detect if running in this platform's CI/CD environment."""
        pass

    @abstractmethod
    def get_changed_files(self, patterns: Optional[List[str]] = None) -> List[Path]:
        """Get list of changed files in the MR/PR."""
        pass

    @abstractmethod
    def post_comment(self, message: str) -> bool:
        """Post validation results as a comment on the MR/PR."""
        pass

    @abstractmethod
    def get_metadata(self) -> dict:
        """Get MR/PR metadata (ID, URL, author, etc.)."""
        pass
