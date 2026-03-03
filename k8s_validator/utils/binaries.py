"""Binary downloader and manager for external tools."""

import hashlib
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import requests


class BinaryManager:
    """Manages external binaries (kubeconform, kubectl)."""

    BINARY_DIR = Path.home() / ".k8s-validator" / "bin"

    # kubeconform download URLs
    KUBECONFORM_VERSION = "0.6.4"
    KUBECONFORM_URLS = {
        (
            "Darwin",
            "x86_64",
        ): f"https://github.com/yannh/kubeconform/releases/download/v{{version}}/kubeconform-darwin-amd64.tar.gz",
        (
            "Darwin",
            "arm64",
        ): f"https://github.com/yannh/kubeconform/releases/download/v{{version}}/kubeconform-darwin-arm64.tar.gz",
        (
            "Linux",
            "x86_64",
        ): f"https://github.com/yannh/kubeconform/releases/download/v{{version}}/kubeconform-linux-amd64.tar.gz",
        (
            "Linux",
            "arm64",
        ): f"https://github.com/yannh/kubeconform/releases/download/v{{version}}/kubeconform-linux-arm64.tar.gz",
    }

    def __init__(self) -> None:
        """Initialize binary manager."""
        self.BINARY_DIR.mkdir(parents=True, exist_ok=True)

    def get_kubeconform_path(self) -> Optional[Path]:
        """Get path to kubeconform binary, downloading if needed."""
        # Check if already in PATH
        system_kubeconform = shutil.which("kubeconform")
        if system_kubeconform:
            return Path(system_kubeconform)

        # Check local cache
        local_kubeconform = self.BINARY_DIR / "kubeconform"
        if local_kubeconform.exists():
            return local_kubeconform

        # Download
        return self._download_kubeconform()

    def _download_kubeconform(self) -> Optional[Path]:
        """Download kubeconform binary."""
        system = platform.system()
        machine = platform.machine()

        # Normalize machine architecture
        if machine in ("aarch64", "arm64"):
            machine = "arm64"
        elif machine in ("x86_64", "amd64"):
            machine = "x86_64"

        url_template = self.KUBECONFORM_URLS.get((system, machine))
        if not url_template:
            return None

        url = url_template.format(version=self.KUBECONFORM_VERSION)

        try:
            # Download tarball
            response = requests.get(url, timeout=60, stream=True)
            response.raise_for_status()

            tarball_path = self.BINARY_DIR / "kubeconform.tar.gz"
            with open(tarball_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Extract binary
            import tarfile

            with tarfile.open(tarball_path, "r:gz") as tar:
                tar.extract("kubeconform", self.BINARY_DIR)

            # Make executable
            binary_path = self.BINARY_DIR / "kubeconform"
            binary_path.chmod(0o755)

            # Clean up tarball
            tarball_path.unlink()

            return binary_path

        except Exception:
            return None

    def get_kubectl_path(self) -> Optional[Path]:
        """Get path to kubectl binary."""
        # kubectl is expected to be in PATH (cluster-specific)
        kubectl = shutil.which("kubectl")
        return Path(kubectl) if kubectl else None

    def verify_binary(self, binary_path: Path) -> bool:
        """Verify binary is executable."""
        if not binary_path.exists():
            return False

        try:
            subprocess.run(
                [str(binary_path), "--version"],
                capture_output=True,
                timeout=5,
            )
            return True
        except Exception:
            return False
