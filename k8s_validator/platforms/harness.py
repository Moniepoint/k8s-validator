"""Harness platform integration."""

import os
import subprocess
from pathlib import Path
from typing import List, Optional

import requests

from k8s_validator.platforms.base import PlatformAdapter


class HarnessAdapter(PlatformAdapter):
    """Harness CI/CD integration."""

    def __init__(self) -> None:
        """Initialize Harness adapter."""
        self.api_key = os.getenv("HARNESS_API_KEY")
        self.account_id = os.getenv("HARNESS_ACCOUNT_ID")
        self.pr_number = os.getenv("HARNESS_PR_NUMBER")
        self.repo_name = os.getenv("HARNESS_REPO_NAME")

    @classmethod
    def detect(cls) -> bool:
        """Detect if running in Harness CI."""
        return all(
            [
                os.getenv("HARNESS_BUILD_ID"),
                os.getenv("HARNESS_PR_NUMBER"),
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
        if not all([self.api_key, self.account_id, self.pr_number]):
            return False

        try:
            # Harness API endpoint for PR comments
            url = f"https://app.harness.io/gateway/code/api/v1/repos/{self.repo_name}/pullreq/{self.pr_number}/comments"

            headers = {
                "x-api-key": self.api_key,
                "Harness-Account": self.account_id,
                "Content-Type": "application/json",
            }

            data = {
                "text": message,
            }

            response = requests.post(url, headers=headers, json=data, timeout=30)
            return response.status_code == 201

        except Exception:
            return False

    def get_metadata(self) -> dict:
        """Get PR metadata."""
        return {
            "platform": "harness",
            "account_id": self.account_id,
            "pr_number": self.pr_number,
            "repo_name": self.repo_name,
        }
