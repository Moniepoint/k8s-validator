"""Core data models for validation."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class Severity(str, Enum):
    """Severity levels for validation findings."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationFinding:
    """A single validation finding."""

    file_path: str
    line: Optional[int] = None
    column: Optional[int] = None
    severity: Severity = Severity.ERROR
    rule_id: str = ""
    message: str = ""
    remediation: str = ""
    resource_kind: Optional[str] = None
    resource_name: Optional[str] = None

    def __str__(self) -> str:
        """String representation."""
        location = f"{self.file_path}"
        if self.line:
            location += f":{self.line}"
        if self.column:
            location += f":{self.column}"
        return f"[{self.severity.value.upper()}] {location} - {self.rule_id}: {self.message}"


@dataclass
class ValidationResult:
    """Result of validating one or more files."""

    findings: List[ValidationFinding] = field(default_factory=list)
    files_checked: int = 0
    files_with_errors: int = 0

    @property
    def error_count(self) -> int:
        """Count of error-level findings."""
        return sum(1 for f in self.findings if f.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count of warning-level findings."""
        return sum(1 for f in self.findings if f.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        """Count of info-level findings."""
        return sum(1 for f in self.findings if f.severity == Severity.INFO)

    @property
    def has_errors(self) -> bool:
        """True if any error-level findings exist."""
        return self.error_count > 0

    def add_finding(self, finding: ValidationFinding) -> None:
        """Add a finding to the result."""
        self.findings.append(finding)

    def merge(self, other: "ValidationResult") -> None:
        """Merge another result into this one."""
        self.findings.extend(other.findings)
        self.files_checked += other.files_checked
        self.files_with_errors += other.files_with_errors


@dataclass
class ValidationConfig:
    """Configuration for validation."""

    # Validators to enable
    enable_syntax: bool = True
    enable_schema: bool = True  # Disabled by default to avoid kubeconform lock issues in CI
    enable_best_practices: bool = True

    # Kubernetes version for schema validation
    kubernetes_version: str = "1.30"

    # CRD schema sources (priority order)
    crd_schema_sources: List[str] = field(
        default_factory=lambda: ["cluster", "catalog", "local", "embedded"]
    )

    # What to do when CRD schema is missing
    on_missing_schema: str = "warning"  # error, warning, skip

    # Severity threshold (findings below this are ignored)
    severity_threshold: Severity = Severity.INFO

    # Rule overrides (rule_id -> enabled)
    rule_overrides: Dict[str, bool] = field(default_factory=dict)

    # Parallel workers for multi-file validation
    parallel_workers: int = 4

    # Paths to exclude from validation
    exclude_paths: List[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, config_path: Path) -> "ValidationConfig":
        """Load configuration from YAML file."""
        import yaml

        if not config_path.exists():
            return cls()

        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

        return cls(
            enable_syntax=data.get("enable_syntax", True),
            enable_schema=data.get("enable_schema", True),
            enable_best_practices=data.get("enable_best_practices", True),
            kubernetes_version=data.get("kubernetes_version", "1.30"),
            crd_schema_sources=data.get(
                "crd_schema_sources", ["cluster", "catalog", "local", "embedded"]
            ),
            on_missing_schema=data.get("on_missing_schema", "warning"),
            severity_threshold=Severity(data.get("severity_threshold", "info")),
            rule_overrides=data.get("rule_overrides", {}),
            parallel_workers=data.get("parallel_workers", 4),
            exclude_paths=data.get("exclude_paths", []),
        )


@dataclass
class CRDInfo:
    """Information about a Custom Resource Definition."""

    group: str
    version: str
    kind: str
    plural: str = ""
    api_version: str = ""

    def __post_init__(self) -> None:
        """Calculate derived fields."""
        if not self.api_version:
            self.api_version = f"{self.group}/{self.version}"
        if not self.plural:
            # Simple pluralization
            self.plural = self.kind.lower() + "s"

    @property
    def full_name(self) -> str:
        """Full CRD name."""
        return f"{self.plural}.{self.group}"
