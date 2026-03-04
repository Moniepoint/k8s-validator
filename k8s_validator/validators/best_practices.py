"""Best practices validation rules for Kubernetes resources."""

from pathlib import Path
from typing import Any, Dict, List

import yaml

from k8s_validator.core.models import Severity, ValidationFinding, ValidationResult


class BestPracticesValidator:
    """Validates Kubernetes resources against best practices."""

    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate a file's manifests against best practices."""
        result = ValidationResult()
        result.files_checked = 1

        try:
            with open(file_path) as f:
                documents = list(yaml.safe_load_all(f))
        except Exception:
            # Skip files that can't be parsed (handled by syntax validator)
            return result

        for doc_idx, manifest in enumerate(documents):
            if not isinstance(manifest, dict):
                continue

            kind = manifest.get("kind", "")
            findings = self._validate_manifest(manifest, file_path, kind)
            result.findings.extend(findings)

        if result.error_count > 0:
            result.files_with_errors = 1

        return result

    def _validate_manifest(
        self,
        manifest: Dict[str, Any],
        file_path: Path,
        kind: str,
    ) -> List[ValidationFinding]:
        """Validate a single manifest."""
        findings: List[ValidationFinding] = []

        # Common checks for all resources
        findings.extend(self._check_labels(manifest, file_path, kind))
        findings.extend(self._check_namespace(manifest, file_path, kind))

        # Kind-specific checks
        if kind in {"Deployment", "StatefulSet", "DaemonSet"}:
            findings.extend(self._check_workload(manifest, file_path, kind))
        elif kind == "Service":
            findings.extend(self._check_service(manifest, file_path))
        elif kind in {"Ingress", "HTTPRoute"}:
            findings.extend(self._check_ingress(manifest, file_path, kind))
        elif kind == "ConfigMap":
            findings.extend(self._check_configmap(manifest, file_path))

        return findings

    def _check_labels(
        self,
        manifest: Dict[str, Any],
        file_path: Path,
        kind: str,
    ) -> List[ValidationFinding]:
        """Check for recommended labels."""
        findings: List[ValidationFinding] = []
        labels = manifest.get("metadata", {}).get("labels", {})

        recommended_labels = ["app", "moniepoint.com/team"]
        missing = [label for label in recommended_labels if label not in labels]

        if missing:
            findings.append(
                ValidationFinding(
                    file_path=str(file_path),
                    severity=Severity.INFO,
                    rule_id="missing-recommended-labels",
                    message=f"Missing recommended labels: {', '.join(missing)}",
                    remediation="Add recommended labels for better organization",
                    resource_kind=kind,
                    resource_name=manifest.get("metadata", {}).get("name"),
                )
            )

        return findings

    def _check_namespace(
        self,
        manifest: Dict[str, Any],
        file_path: Path,
        kind: str,
    ) -> List[ValidationFinding]:
        """Check namespace is not default."""
        findings: List[ValidationFinding] = []
        namespace = manifest.get("metadata", {}).get("namespace")

        if namespace == "default":
            findings.append(
                ValidationFinding(
                    file_path=str(file_path),
                    severity=Severity.WARNING,
                    rule_id="default-namespace",
                    message="Resource deployed to 'default' namespace",
                    remediation="Use a dedicated namespace instead of 'default'",
                    resource_kind=kind,
                    resource_name=manifest.get("metadata", {}).get("name"),
                )
            )

        return findings

    def _check_workload(
        self,
        manifest: Dict[str, Any],
        file_path: Path,
        kind: str,
    ) -> List[ValidationFinding]:
        """Check workload resources (Deployment, StatefulSet, DaemonSet)."""
        findings: List[ValidationFinding] = []
        spec = manifest.get("spec", {})
        template_spec = spec.get("template", {}).get("spec", {})
        containers = template_spec.get("containers", [])

        resource_name = manifest.get("metadata", {}).get("name")

        # Check replicas for HA (Deployment only)
        if kind == "Deployment":
            replicas = spec.get("replicas", 1)
            if replicas < 2:
                findings.append(
                    ValidationFinding(
                        file_path=str(file_path),
                        severity=Severity.WARNING,
                        rule_id="low-replica-count",
                        message=f"Only {replicas} replica(s) configured",
                        remediation="Use 2+ replicas for high availability",
                        resource_kind=kind,
                        resource_name=resource_name,
                    )
                )

        # Check each container
        for container in containers:
            container_name = container.get("name", "unknown")

            # Check resource limits
            resources = container.get("resources", {})
            if not resources.get("limits"):
                findings.append(
                    ValidationFinding(
                        file_path=str(file_path),
                        severity=Severity.ERROR,
                        rule_id="missing-resource-limits",
                        message=f"Container '{container_name}' has no resource limits",
                        remediation="Add CPU and memory limits to prevent resource exhaustion",
                        resource_kind=kind,
                        resource_name=resource_name,
                    )
                )

            # Check resource requests
            if not resources.get("requests"):
                findings.append(
                    ValidationFinding(
                        file_path=str(file_path),
                        severity=Severity.ERROR,
                        rule_id="missing-resource-requests",
                        message=f"Container '{container_name}' has no resource requests",
                        remediation="Add CPU and memory requests for proper scheduling",
                        resource_kind=kind,
                        resource_name=resource_name,
                    )
                )

            # Check probes
            if not container.get("livenessProbe"):
                findings.append(
                    ValidationFinding(
                        file_path=str(file_path),
                        severity=Severity.WARNING,
                        rule_id="missing-liveness-probe",
                        message=f"Container '{container_name}' has no liveness probe",
                        remediation="Add liveness probe to detect and restart unhealthy containers",
                        resource_kind=kind,
                        resource_name=resource_name,
                    )
                )

            if not container.get("readinessProbe"):
                findings.append(
                    ValidationFinding(
                        file_path=str(file_path),
                        severity=Severity.WARNING,
                        rule_id="missing-readiness-probe",
                        message=f"Container '{container_name}' has no readiness probe",
                        remediation="Add readiness probe to control traffic routing",
                        resource_kind=kind,
                        resource_name=resource_name,
                    )
                )

            # Check image tag is not 'latest'
            image = container.get("image", "")
            if image.endswith(":latest") or ":" not in image:
                findings.append(
                    ValidationFinding(
                        file_path=str(file_path),
                        severity=Severity.WARNING,
                        rule_id="image-latest-tag",
                        message=f"Container '{container_name}' uses 'latest' or no tag",
                        remediation="Use specific version tags for reproducibility",
                        resource_kind=kind,
                        resource_name=resource_name,
                    )
                )

            # Check security context
            security_context = container.get("securityContext", {})
            if not security_context.get("runAsNonRoot"):
                findings.append(
                    ValidationFinding(
                        file_path=str(file_path),
                        severity=Severity.WARNING,
                        rule_id="missing-run-as-non-root",
                        message=f"Container '{container_name}' may run as root",
                        remediation="Set runAsNonRoot: true for better security",
                        resource_kind=kind,
                        resource_name=resource_name,
                    )
                )

        return findings

    def _check_service(
        self,
        manifest: Dict[str, Any],
        file_path: Path,
    ) -> List[ValidationFinding]:
        """Check Service resources."""
        findings: List[ValidationFinding] = []
        spec = manifest.get("spec", {})

        # Check selector exists
        if not spec.get("selector"):
            findings.append(
                ValidationFinding(
                    file_path=str(file_path),
                    severity=Severity.ERROR,
                    rule_id="missing-service-selector",
                    message="Service has no selector defined",
                    remediation="Add selector to match pod labels",
                    resource_kind="Service",
                    resource_name=manifest.get("metadata", {}).get("name"),
                )
            )

        return findings

    def _check_ingress(
        self,
        manifest: Dict[str, Any],
        file_path: Path,
        kind: str,
    ) -> List[ValidationFinding]:
        """Check Ingress/HTTPRoute resources."""
        findings: List[ValidationFinding] = []
        spec = manifest.get("spec", {})

        # Check for TLS configuration
        tls_configured = bool(spec.get("tls")) if kind == "Ingress" else False

        if not tls_configured:
            findings.append(
                ValidationFinding(
                    file_path=str(file_path),
                    severity=Severity.WARNING,
                    rule_id="missing-ingress-tls",
                    message="Ingress has no TLS configuration",
                    remediation="Configure TLS for secure HTTPS access",
                    resource_kind=kind,
                    resource_name=manifest.get("metadata", {}).get("name"),
                )
            )

        return findings

    def _check_configmap(
        self,
        manifest: Dict[str, Any],
        file_path: Path,
    ) -> List[ValidationFinding]:
        """Check ConfigMap resources."""
        findings: List[ValidationFinding] = []
        data = manifest.get("data") or {}

        # Check for potentially sensitive data
        sensitive_patterns = ["password", "secret", "token", "key", "credential"]

        for key in data.keys():
            key_lower = key.lower()
            if any(pattern in key_lower for pattern in sensitive_patterns):
                findings.append(
                    ValidationFinding(
                        file_path=str(file_path),
                        severity=Severity.WARNING,
                        rule_id="sensitive-data-in-configmap",
                        message=f"ConfigMap key '{key}' may contain sensitive data",
                        remediation="Use Secrets instead of ConfigMaps for sensitive data",
                        resource_kind="ConfigMap",
                        resource_name=manifest.get("metadata", {}).get("name"),
                    )
                )

        return findings
