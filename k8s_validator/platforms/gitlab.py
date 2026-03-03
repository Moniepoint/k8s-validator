"""GitLab platform integration."""

import os
import subprocess
from pathlib import Path
from typing import Any, List, Optional

try:
    import gitlab
except ImportError:
    gitlab = None

from k8s_validator.platforms.base import PlatformAdapter


class GitLabAdapter(PlatformAdapter):
    """GitLab CI/CD integration."""

    def __init__(self) -> None:
        """Initialize GitLab adapter."""
        self.gitlab_url = os.getenv("CI_SERVER_URL", "https://gitlab.com")
        self.project_id = os.getenv("CI_PROJECT_ID")
        self.mr_iid = os.getenv("CI_MERGE_REQUEST_IID")
        self.token = os.getenv("GITLAB_TOKEN") or os.getenv("CI_JOB_TOKEN")

        self._client: Optional[Any] = None
        self._project: Optional[Any] = None
        self._mr: Optional[Any] = None

    @classmethod
    def detect(cls) -> bool:
        """Detect if running in GitLab CI."""
        return all(
            [
                os.getenv("GITLAB_CI") == "true",
                os.getenv("CI_MERGE_REQUEST_IID"),
            ]
        )

    def get_changed_files(self, patterns: Optional[List[str]] = None) -> List[Path]:
        """Get list of changed files in the MR."""
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

                    # Check if file matches patterns
                    for pattern in patterns:
                        if path.match(pattern):
                            if path.exists():
                                changed_files.append(path)
                            break

        except Exception:
            pass

        return changed_files

    def post_comment(self, message: str) -> bool:
        """Post validation results as MR comment."""
        if not self._ensure_authenticated():
            return False

        try:
            # Post comment on MR
            self._mr.notes.create({"body": message})
            return True

        except Exception:
            return False

    def get_metadata(self) -> dict:
        """Get MR metadata."""
        metadata = {
            "platform": "gitlab",
            "project_id": self.project_id,
            "mr_iid": self.mr_iid,
            "gitlab_url": self.gitlab_url,
        }

        if self._ensure_authenticated():
            try:
                metadata["mr_title"] = self._mr.title
                metadata["mr_author"] = self._mr.author.get("username")
                metadata["mr_url"] = self._mr.web_url
                metadata["source_branch"] = self._mr.source_branch
                metadata["target_branch"] = self._mr.target_branch
            except Exception:
                pass

        return metadata

    def _ensure_authenticated(self) -> bool:
        """Ensure GitLab API is authenticated."""
        if not gitlab:
            return False

        if not all([self.project_id, self.mr_iid, self.token]):
            return False

        if self._mr:
            return True

        try:
            # Initialize GitLab client
            self._client = gitlab.Gitlab(self.gitlab_url, private_token=self.token)
            self._client.auth()

            # Get project and MR
            self._project = self._client.projects.get(self.project_id)
            self._mr = self._project.mergerequests.get(self.mr_iid)

            return True

        except Exception:
            return False
