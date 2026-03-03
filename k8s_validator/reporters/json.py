"""JSON reporter."""

import json
from datetime import datetime
from typing import Any, Dict, List

from k8s_validator.core.models import ValidationResult


class JSONReporter:
    """Reports validation results as JSON."""

    def report(self, result: ValidationResult) -> str:
        """Generate JSON report."""
        findings_data: List[Dict[str, Any]] = []

        for finding in result.findings:
            findings_data.append(
                {
                    "file": finding.file_path,
                    "line": finding.line,
                    "column": finding.column,
                    "severity": finding.severity.value,
                    "rule_id": finding.rule_id,
                    "message": finding.message,
                    "remediation": finding.remediation,
                    "resource_kind": finding.resource_kind,
                    "resource_name": finding.resource_name,
                }
            )

        report_data = {
            "findings": findings_data,
            "summary": {
                "files_checked": result.files_checked,
                "files_with_errors": result.files_with_errors,
                "error_count": result.error_count,
                "warning_count": result.warning_count,
                "info_count": result.info_count,
            },
            "metadata": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "tool": "k8s-manifest-validator",
                "version": "0.1.0",
            },
        }

        return json.dumps(report_data, indent=2)
