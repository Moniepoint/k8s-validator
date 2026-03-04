"""Kubernetes schema validation using kubeconform."""

import fcntl
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from k8s_validator.core.models import CRDInfo, Severity, ValidationFinding, ValidationResult
from k8s_validator.crds.detector import CRDDetector
from k8s_validator.crds.schema_loader import CRDSchemaLoader
from k8s_validator.utils.binaries import BinaryManager


class SchemaValidator:
    """Validates Kubernetes resources against schemas."""

    def __init__(
        self,
        kubernetes_version: str = "1.30",
        crd_schema_sources: Optional[List[str]] = None,
    ) -> None:
        """Initialize schema validator."""
        self.kubernetes_version = kubernetes_version
        self.crd_schema_sources = crd_schema_sources or ["cluster", "catalog", "local", "embedded"]
        self.binary_manager = BinaryManager()
        self.crd_detector = CRDDetector()
        self.crd_schema_loader = CRDSchemaLoader()
        self._kubeconform_path: Optional[Path] = None

    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate a file's schemas."""
        result = ValidationResult()
        result.files_checked = 1

        # Get kubeconform binary
        if not self._kubeconform_path:
            self._kubeconform_path = self.binary_manager.get_kubeconform_path()

        if not self._kubeconform_path:
            # Fallback to basic schema validation if kubeconform not available
            return self._validate_with_fallback(file_path)

        # Run kubeconform
        try:
            findings = self._run_kubeconform(file_path)
            result.findings = findings
            if any(f.severity == Severity.ERROR for f in findings):
                result.files_with_errors = 1
        except Exception as e:
            result.add_finding(
                ValidationFinding(
                    file_path=str(file_path),
                    severity=Severity.ERROR,
                    rule_id="schema-validation-error",
                    message=f"Schema validation failed: {e}",
                )
            )
            result.files_with_errors = 1

        return result

    def _run_kubeconform(self, file_path: Path) -> List[ValidationFinding]:
        """Run kubeconform on a file with file locking to prevent concurrent access."""
        findings: List[ValidationFinding] = []

        # Build kubeconform command
        cmd = [
            str(self._kubeconform_path),
            "-output",
            "json",
            "-summary",
            "-kubernetes-version",
            self.kubernetes_version,
            "-strict",
            str(file_path),
        ]

        # Add CRD schema locations
        # kubeconform supports additional schema locations for CRDs
        cmd.extend(
            [
                "-schema-location",
                "default",  # Built-in K8s schemas
                "-schema-location",
                "https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json",
            ]
        )

        # Create lock file to prevent concurrent access to kubeconform binary
        if not self._kubeconform_path:
            findings.append(
                ValidationFinding(
                    file_path=str(file_path),
                    severity=Severity.ERROR,
                    rule_id="schema-error",
                    message="kubeconform binary not found",
                )
            )
            return findings

        lock_file_path = self._kubeconform_path.parent / ".kubeconform.lock"
        lock_file = None

        try:
            # Acquire exclusive lock with timeout to prevent concurrent binary access
            lock_file = open(lock_file_path, "w")
            max_wait = 30  # seconds
            start_time = time.time()

            while True:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break  # Lock acquired
                except IOError:
                    if time.time() - start_time > max_wait:
                        raise TimeoutError("Could not acquire kubeconform lock after 30s")
                    time.sleep(0.1)  # Wait 100ms before retry

            # Run kubeconform with lock held
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Parse JSON output
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue

                    try:
                        validation_result = json.loads(line)

                        # Skip summary lines
                        if "resources" in validation_result:
                            continue

                        # Parse validation error
                        if validation_result.get("status") == "statusInvalid":
                            findings.append(
                                ValidationFinding(
                                    file_path=str(file_path),
                                    severity=Severity.ERROR,
                                    rule_id="schema-validation",
                                    message=validation_result.get(
                                        "msg", "Schema validation failed"
                                    ),
                                    remediation="Fix the schema validation error",
                                    resource_kind=validation_result.get("kind"),
                                    resource_name=validation_result.get("name"),
                                )
                            )
                        elif validation_result.get("status") == "statusError":
                            findings.append(
                                ValidationFinding(
                                    file_path=str(file_path),
                                    severity=Severity.ERROR,
                                    rule_id="schema-error",
                                    message=validation_result.get("msg", "Schema error"),
                                    resource_kind=validation_result.get("kind"),
                                )
                            )

                    except json.JSONDecodeError:
                        continue

        except subprocess.TimeoutExpired:
            findings.append(
                ValidationFinding(
                    file_path=str(file_path),
                    severity=Severity.ERROR,
                    rule_id="schema-timeout",
                    message="Schema validation timed out",
                )
            )
        except Exception as e:
            findings.append(
                ValidationFinding(
                    file_path=str(file_path),
                    severity=Severity.ERROR,
                    rule_id="schema-error",
                    message=f"Schema validation error: {e}",
                )
            )
        finally:
            # Always release the lock
            if lock_file:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    lock_file.close()
                except Exception:
                    pass  # Ignore errors when releasing lock

        return findings

    def _validate_with_fallback(self, file_path: Path) -> ValidationResult:
        """Fallback validation without kubeconform."""
        result = ValidationResult()
        result.files_checked = 1

        # Just check that manifests are valid YAML and have required fields
        try:
            with open(file_path) as f:
                documents = list(yaml.safe_load_all(f))

            for doc_idx, manifest in enumerate(documents):
                if not isinstance(manifest, dict):
                    continue

                # Check required fields
                if "apiVersion" not in manifest:
                    result.add_finding(
                        ValidationFinding(
                            file_path=str(file_path),
                            severity=Severity.ERROR,
                            rule_id="missing-api-version",
                            message="Missing required field: apiVersion",
                            remediation="Add apiVersion field to the manifest",
                        )
                    )

                if "kind" not in manifest:
                    result.add_finding(
                        ValidationFinding(
                            file_path=str(file_path),
                            severity=Severity.ERROR,
                            rule_id="missing-kind",
                            message="Missing required field: kind",
                            remediation="Add kind field to the manifest",
                        )
                    )

        except Exception as e:
            result.add_finding(
                ValidationFinding(
                    file_path=str(file_path),
                    severity=Severity.ERROR,
                    rule_id="schema-validation-error",
                    message=f"Schema validation failed: {e}",
                )
            )
            result.files_with_errors = 1

        if result.error_count > 0:
            result.files_with_errors = 1

        return result
