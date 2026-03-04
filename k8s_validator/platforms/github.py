"""GitHub platform integration."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, List, Optional

try:
    from github import Github
except ImportError:
    Github = None

from k8s_validator.platforms.base import PlatformAdapter


class GitHubAdapter(PlatformAdapter):
    """GitHub Actions integration."""

    def __init__(self) -> None:
        """Initialize GitHub adapter."""
        self.repository = os.getenv("GITHUB_REPOSITORY")  # owner/repo
        self.token = os.getenv("GITHUB_TOKEN")
        self.event_name = os.getenv("GITHUB_EVENT_NAME")

        # Get PR number from event file
        self.pr_number = self._get_pr_number()
        self.base_ref = self._get_base_ref()

        self._client: Optional[Any] = None
        self._repo: Optional[Any] = None
        self._pr: Optional[Any] = None

    def _get_pr_number(self) -> Optional[str]:
        """Extract PR number from GitHub event."""
        event_path = os.getenv("GITHUB_EVENT_PATH")
        if not event_path or not Path(event_path).exists():
            return None

        try:
            with open(event_path) as f:
                event_data = json.load(f)
                # For pull_request events
                if "pull_request" in event_data:
                    return str(event_data["pull_request"]["number"])
                # For pull_request_target events
                if "number" in event_data:
                    return str(event_data["number"])
        except Exception:
            pass

        return None

    def _get_base_ref(self) -> str:
        """Get base branch from GitHub event or default to main."""
        event_path = os.getenv("GITHUB_EVENT_PATH")
        if not event_path or not Path(event_path).exists():
            return "main"

        try:
            with open(event_path) as f:
                event_data = json.load(f)
                if "pull_request" in event_data:
                    return event_data["pull_request"]["base"]["ref"]
        except Exception:
            pass

        return os.getenv("GITHUB_BASE_REF", "main")

    @classmethod
    def detect(cls) -> bool:
        """Detect if running in GitHub Actions for a PR."""
        if os.getenv("GITHUB_ACTIONS") != "true":
            return False

        event_name = os.getenv("GITHUB_EVENT_NAME")
        return event_name in ["pull_request", "pull_request_target"]

    def get_changed_files(self, patterns: Optional[List[str]] = None) -> List[Path]:
        """Get list of changed files in the PR."""
        if not patterns:
            patterns = ["*.yaml", "*.yml", "*.json"]

        changed_files: List[Path] = []

        try:
            # Fetch the base branch to ensure up-to-date comparison
            subprocess.run(
                ["git", "fetch", "origin", self.base_ref],
                capture_output=True,
                timeout=30,
            )

            # Get changed files comparing PR head to base
            result = subprocess.run(
                ["git", "diff", "--name-only", f"origin/{self.base_ref}...HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                all_changed = [f for f in result.stdout.strip().split("\n") if f]
                for file_path in all_changed:
                    path = Path(file_path)
                    # Check if file matches patterns and exists
                    if self._matches_pattern(path, patterns) and path.exists():
                        changed_files.append(path)

        except Exception:
            pass

        return changed_files

    def _matches_pattern(self, path: Path, patterns: List[str]) -> bool:
        """Check if path matches any of the given patterns."""
        for pattern in patterns:
            if path.match(pattern):
                return True
        return False

    def post_comment(self, message: str) -> bool:
        """Post validation results as PR comment."""
        if not self._ensure_authenticated():
            return False

        try:
            # Post comment on PR
            self._pr.create_issue_comment(message)
            return True

        except Exception:
            return False

    def get_metadata(self) -> dict:
        """Get PR metadata."""
        metadata = {
            "platform": "github",
            "repository": self.repository,
            "pr_number": self.pr_number,
        }

        if self._ensure_authenticated():
            try:
                metadata["pr_title"] = self._pr.title
                metadata["pr_author"] = self._pr.user.login
                metadata["pr_url"] = self._pr.html_url
                metadata["head_branch"] = self._pr.head.ref
                metadata["base_branch"] = self._pr.base.ref
            except Exception:
                pass

        return metadata

    def _ensure_authenticated(self) -> bool:
        """Ensure GitHub API is authenticated."""
        if not Github:
            return False

        if not all([self.repository, self.pr_number, self.token]):
            return False

        if self._pr:
            return True

        try:
            # Initialize GitHub client
            self._client = Github(self.token)

            # Get repository and PR
            self._repo = self._client.get_repo(self.repository)
            self._pr = self._repo.get_pull(int(self.pr_number))

            return True

        except Exception:
            return False
