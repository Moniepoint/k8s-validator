"""Markdown reporter for MR/PR comments."""

from typing import Dict, List

from k8s_validator.core.models import Severity, ValidationResult


class MarkdownReporter:
    """Reports validation results as Markdown for GitLab/GitHub comments."""

    def report(self, result: ValidationResult) -> str:
        """Generate Markdown report."""
        lines: List[str] = []

        # Header
        lines.append("## 🔍 K8s Manifest Validation Results")
        lines.append("")

        # Summary
        emoji = "✅" if not result.has_errors else "❌"
        lines.append(f"**Summary**: {emoji} ")

        parts = []
        if result.error_count:
            parts.append(f"{result.error_count} error{'s' if result.error_count != 1 else ''}")
        if result.warning_count:
            parts.append(
                f"{result.warning_count} warning{'s' if result.warning_count != 1 else ''}"
            )
        if result.info_count:
            parts.append(f"{result.info_count} info")

        if parts:
            lines.append(", ".join(parts) + f" across {result.files_checked} file(s)")
        else:
            lines.append(f"No issues found in {result.files_checked} file(s)")

        lines.append("")

        if not result.findings:
            return "\n".join(lines)

        # Group by severity
        errors = [f for f in result.findings if f.severity == Severity.ERROR]
        warnings = [f for f in result.findings if f.severity == Severity.WARNING]
        infos = [f for f in result.findings if f.severity == Severity.INFO]

        # Errors section
        if errors:
            lines.append("### ❌ Errors")
            lines.append("")
            lines.extend(self._format_findings(errors))
            lines.append("")

        # Warnings section
        if warnings:
            lines.append("### ⚠️ Warnings")
            lines.append("")
            lines.extend(self._format_findings(warnings))
            lines.append("")

        # Info section
        if infos:
            lines.append("<details>")
            lines.append("<summary>ℹ️ Info (click to expand)</summary>")
            lines.append("")
            lines.extend(self._format_findings(infos))
            lines.append("")
            lines.append("</details>")

        return "\n".join(lines)

    def _format_findings(self, findings: List) -> List[str]:
        """Format findings as markdown."""
        lines: List[str] = []

        # Group by file
        by_file: Dict[str, List] = {}
        for finding in findings:
            if finding.file_path not in by_file:
                by_file[finding.file_path] = []
            by_file[finding.file_path].append(finding)

        for file_path, file_findings in sorted(by_file.items()):
            lines.append(f"**{file_path}**")
            lines.append("")
            lines.append("| Line | Rule | Message |")
            lines.append("|------|------|---------|")

            for finding in sorted(file_findings, key=lambda f: f.line or 0):
                line = str(finding.line) if finding.line else "-"
                message = finding.message.replace("|", "\\|")
                lines.append(f"| {line} | `{finding.rule_id}` | {message} |")

            lines.append("")

        return lines
