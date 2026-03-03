"""YAML and JSON syntax validation."""

import json
from pathlib import Path
from typing import List

import yaml
from yamllint import config, linter

from k8s_validator.core.models import Severity, ValidationFinding, ValidationResult


class SyntaxValidator:
    """Validates YAML and JSON syntax."""

    def __init__(self) -> None:
        """Initialize syntax validator."""
        # yamllint configuration
        self.yamllint_config = config.YamlLintConfig(
            "extends: default\n"
            "rules:\n"
            "  line-length: {max: 3000}\n"
            "  indentation: {spaces: 2}\n"
        )

    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate a single file's syntax."""
        result = ValidationResult()
        result.files_checked = 1

        try:
            content = file_path.read_text()
        except Exception as e:
            result.add_finding(
                ValidationFinding(
                    file_path=str(file_path),
                    severity=Severity.ERROR,
                    rule_id="syntax-read-error",
                    message=f"Failed to read file: {e}",
                )
            )
            result.files_with_errors = 1
            return result

        # Determine file type
        suffix = file_path.suffix.lower()

        if suffix in {".yaml", ".yml"}:
            findings = self._validate_yaml(file_path, content)
        elif suffix == ".json":
            findings = self._validate_json(file_path, content)
        else:
            # Try YAML first, then JSON
            yaml_findings = self._validate_yaml(file_path, content)
            if yaml_findings:
                json_findings = self._validate_json(file_path, content)
                findings = (
                    yaml_findings if len(yaml_findings) <= len(json_findings) else json_findings
                )
            else:
                findings = yaml_findings

        result.findings = findings
        if any(f.severity == Severity.ERROR for f in findings):
            result.files_with_errors = 1

        return result

    def _validate_yaml(self, file_path: Path, content: str) -> List[ValidationFinding]:
        """Validate YAML syntax."""
        findings: List[ValidationFinding] = []

        # First, try to parse as YAML
        try:
            list(yaml.safe_load_all(content))
        except yaml.YAMLError as e:
            findings.append(
                ValidationFinding(
                    file_path=str(file_path),
                    line=getattr(e, "problem_mark", None) and e.problem_mark.line + 1,
                    column=getattr(e, "problem_mark", None) and e.problem_mark.column + 1,
                    severity=Severity.ERROR,
                    rule_id="yaml-parse-error",
                    message=f"YAML parsing error: {e.problem or str(e)}",
                    remediation="Fix YAML syntax errors",
                )
            )
            return findings

        # Run yamllint for style checks
        for problem in linter.run(content, self.yamllint_config, file_path):
            findings.append(
                ValidationFinding(
                    file_path=str(file_path),
                    line=problem.line,
                    column=problem.column,
                    severity=Severity.WARNING if problem.level == "warning" else Severity.ERROR,
                    rule_id=f"yaml-{problem.rule}",
                    message=problem.desc or problem.message,
                    remediation=f"See yamllint rule: {problem.rule}",
                )
            )

        return findings

    def _validate_json(self, file_path: Path, content: str) -> List[ValidationFinding]:
        """Validate JSON syntax."""
        findings: List[ValidationFinding] = []

        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            findings.append(
                ValidationFinding(
                    file_path=str(file_path),
                    line=e.lineno,
                    column=e.colno,
                    severity=Severity.ERROR,
                    rule_id="json-parse-error",
                    message=f"JSON parsing error: {e.msg}",
                    remediation="Fix JSON syntax errors",
                )
            )

        return findings
