"""Console reporter with colored output."""

from typing import Dict, List

from rich.console import Console
from rich.table import Table

from k8s_validator.core.models import Severity, ValidationResult


class ConsoleReporter:
    """Reports validation results to console."""

    def __init__(self, use_color: bool = True) -> None:
        """Initialize console reporter."""
        self.console = Console(no_color=not use_color)

    def report(self, result: ValidationResult) -> str:
        """Generate console report."""
        # Summary
        self.console.print()
        self.console.print("[bold]Validation Summary[/bold]")
        self.console.print(f"Files checked: {result.files_checked}")
        self.console.print(f"Errors: [red]{result.error_count}[/red]")
        self.console.print(f"Warnings: [yellow]{result.warning_count}[/yellow]")
        self.console.print(f"Info: [blue]{result.info_count}[/blue]")
        self.console.print()

        if not result.findings:
            self.console.print("[green]✓ No issues found[/green]")
            return ""

        # Group findings by file
        by_file: Dict[str, List] = {}
        for finding in result.findings:
            if finding.file_path not in by_file:
                by_file[finding.file_path] = []
            by_file[finding.file_path].append(finding)

        # Print findings by file
        for file_path, findings in sorted(by_file.items()):
            self.console.print(f"[bold]{file_path}[/bold]")

            for finding in sorted(findings, key=lambda f: (f.severity.value, f.line or 0)):
                color = self._severity_color(finding.severity)
                location = f":{finding.line}" if finding.line else ""
                self.console.print(
                    f"  [{color}]{finding.severity.value.upper()}[/{color}]"
                    f"{location} "
                    f"[{finding.rule_id}] {finding.message}"
                )
                if finding.remediation:
                    self.console.print(f"    → {finding.remediation}", style="dim")

            self.console.print()

        return ""

    def _severity_color(self, severity: Severity) -> str:
        """Get color for severity."""
        return {
            Severity.ERROR: "red",
            Severity.WARNING: "yellow",
            Severity.INFO: "blue",
        }[severity]
