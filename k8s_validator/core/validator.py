"""Main validator orchestrator."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional

from k8s_validator.core.models import ValidationConfig, ValidationResult
from k8s_validator.validators.syntax import SyntaxValidator
from k8s_validator.validators.best_practices import BestPracticesValidator
from k8s_validator.validators.schema import SchemaValidator


class K8sManifestValidator:
    """Main validator that orchestrates all validation layers."""

    def __init__(self, config: Optional[ValidationConfig] = None) -> None:
        """Initialize validator."""
        self.config = config or ValidationConfig()

        # Initialize validators
        self.syntax_validator = SyntaxValidator() if self.config.enable_syntax else None
        self.schema_validator = (
            SchemaValidator(
                kubernetes_version=self.config.kubernetes_version,
                crd_schema_sources=self.config.crd_schema_sources,
            )
            if self.config.enable_schema
            else None
        )
        self.best_practices_validator = (
            BestPracticesValidator() if self.config.enable_best_practices else None
        )

    def validate_files(self, file_paths: List[Path]) -> ValidationResult:
        """Validate multiple files in parallel."""
        overall_result = ValidationResult()

        # Filter out excluded paths
        files_to_validate = [
            f
            for f in file_paths
            if not any(str(f).startswith(exclude) for exclude in self.config.exclude_paths)
        ]

        if not files_to_validate:
            return overall_result

        # Validate in parallel
        with ThreadPoolExecutor(max_workers=self.config.parallel_workers) as executor:
            future_to_file = {
                executor.submit(self.validate_file, file_path): file_path
                for file_path in files_to_validate
            }

            for future in as_completed(future_to_file):
                file_result = future.result()
                overall_result.merge(file_result)

        return overall_result

    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate a single file through all enabled validators."""
        overall_result = ValidationResult()
        overall_result.files_checked = 1

        # 1. Syntax validation
        if self.syntax_validator:
            syntax_result = self.syntax_validator.validate_file(file_path)
            overall_result.merge(syntax_result)

            # If syntax errors, skip further validation
            if syntax_result.error_count > 0:
                return overall_result

        # 2. Schema validation
        if self.schema_validator:
            schema_result = self.schema_validator.validate_file(file_path)
            overall_result.merge(schema_result)

        # 3. Best practices validation
        if self.best_practices_validator:
            bp_result = self.best_practices_validator.validate_file(file_path)
            overall_result.merge(bp_result)

        # Filter by severity threshold
        overall_result.findings = [
            f for f in overall_result.findings if self._meets_threshold(f.severity)
        ]

        return overall_result

    def _meets_threshold(self, severity) -> bool:
        """Check if severity meets configured threshold."""
        severity_order = {"error": 3, "warning": 2, "info": 1}
        return severity_order.get(severity.value, 0) >= severity_order.get(
            self.config.severity_threshold.value, 0
        )

    @classmethod
    def from_config_file(cls, config_path: Path) -> "K8sManifestValidator":
        """Create validator from config file."""
        config = ValidationConfig.from_file(config_path)
        return cls(config)
