"""GitHub platform integration."""

import os
import subprocess
from pathlib import Path
from typing import List, Optional

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
        self.pr_number = os.getenv("GITHUB_PR_NUMBER")
        self.token = os.getenv("GITHUB_TOKEN")

        self._client: Optional[Any] = None
        self._repo: Optional[Any] = None
        self._pr: Optional[Any] = None

    @classmethod
    def detect(cls) -> bool:
        """Detect if running in GitHub Actions."""
        return all(
            [
                os.getenv("GITHUB_ACTIONS") == "true",
                os.getenv("GITHUB_PR_NUMBER"),
            ]
        )

    def get_changed_files(self, patterns: Optional[List[str]] = None) -> List[Path]:
        """Get list of changed files in the PR."""
        if not patterns:
            patterns = ["*.yaml", "*.yml", "*.json"]

        changed_files: List[Path] = []

        try:
            # Get changed files from git
            result = subprocess.run(
                ["git", "diff", "--name-only", "origin/main...HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                for file_path in result.stdout.strip().split("\n"):
                    if not file_path:
                        continue

                    path = Path(file_path)

                    for pattern in patterns:
                        if path.match(pattern):
                            if path.exists():
                                changed_files.append(path)
                            break

        except Exception:
            pass

        return changed_files

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
