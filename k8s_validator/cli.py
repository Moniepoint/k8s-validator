"""Command-line interface for k8s-validator."""

import sys
from pathlib import Path
from typing import List, Optional

import click

from k8s_validator.core.validator import K8sManifestValidator
from k8s_validator.core.models import ValidationConfig, Severity
from k8s_validator.reporters.console import ConsoleReporter
from k8s_validator.reporters.json import JSONReporter
from k8s_validator.reporters.markdown import MarkdownReporter


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """K8s Manifest Validator - Validate Kubernetes manifests and CRDs."""
    pass


@cli.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Config file path (optional)",
)
@click.option(
    "--format",
    type=click.Choice(["console", "json", "markdown"]),
    default="console",
    help="Output format",
)
@click.option(
    "--severity",
    type=click.Choice(["error", "warning", "info"]),
    default="info",
    help="Minimum severity level",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Output file (default: stdout)",
)
@click.option("--no-color", is_flag=True, help="Disable colored output")
@click.option("--strict", is_flag=True, help="Exit with error on any finding")
def validate(
    files: tuple,
    config: Optional[Path],
    format: str,
    severity: str,
    output: Optional[Path],
    no_color: bool,
    strict: bool,
) -> None:
    """Validate Kubernetes manifest files."""
    # Load or create config
    if config and config.exists():
        validator = K8sManifestValidator.from_config_file(config)
    else:
        # Try default config file
        default_config = Path(".k8s-validator.yaml")
        if default_config.exists():
            validator = K8sManifestValidator.from_config_file(default_config)
        else:
            validator_config = ValidationConfig()
            validator_config.severity_threshold = Severity(severity)
            validator = K8sManifestValidator(validator_config)

    # Collect all YAML/JSON files
    file_list: List[Path] = []
    for file_path in files:
        if file_path.is_dir():
            file_list.extend(file_path.rglob("*.yaml"))
            file_list.extend(file_path.rglob("*.yml"))
            file_list.extend(file_path.rglob("*.json"))
        else:
            file_list.append(file_path)

    if not file_list:
        click.echo("No files to validate", err=True)
        sys.exit(1)

    # Validate
    result = validator.validate_files(file_list)

    # Generate report
    if format == "console":
        reporter = ConsoleReporter(use_color=not no_color)
        reporter.report(result)
        report_text = ""
    elif format == "json":
        reporter = JSONReporter()
        report_text = reporter.report(result)
    elif format == "markdown":
        reporter = MarkdownReporter()
        report_text = reporter.report(result)
    else:
        report_text = ""

    # Output
    if output and report_text:
        output.write_text(report_text)
        click.echo(f"Report written to {output}")
    elif report_text:
        click.echo(report_text)

    # Exit code
    if result.has_errors:
        sys.exit(1)
    elif strict and result.findings:
        sys.exit(1)
    else:
        sys.exit(0)


@cli.command()
def init() -> None:
    """Create a default .k8s-validator.yaml config file."""
    config_path = Path(".k8s-validator.yaml")

    if config_path.exists():
        click.echo("Config file already exists", err=True)
        sys.exit(1)

    default_config = """# K8s Manifest Validator Configuration

# Enable/disable validators
enable_syntax: true
enable_schema: true
enable_best_practices: true

# Kubernetes version for schema validation
kubernetes_version: "1.30"

# CRD schema sources (priority order)
crd_schema_sources:
  - cluster    # Extract from current cluster via kubectl
  - catalog    # Download from Datree CRD catalog
  - local      # Load from .k8s-validator/crds/
  - embedded   # Use pre-packaged schemas

# What to do when CRD schema is missing
on_missing_schema: warning  # error, warning, or skip

# Minimum severity to report (error, warning, info)
severity_threshold: info

# Parallel workers for file validation
parallel_workers: 4

# Rule overrides (rule_id: enabled)
rule_overrides:
  # Example: disable specific rules
  # missing-recommended-labels: false

# Paths to exclude from validation
exclude_paths:
  - .git/
  - node_modules/
  - vendor/
"""

    config_path.write_text(default_config)
    click.echo(f"Created {config_path}")


@cli.command()
def version() -> None:
    """Show version information."""
    click.echo("k8s-validator version 0.1.0")


def main() -> None:
    """Entry point."""
    cli()


if __name__ == "__main__":
    main()


@cli.command()
@click.option(
    "--platform",
    type=click.Choice(["auto", "gitlab", "github", "harness"]),
    default="auto",
    help="CI/CD platform (auto-detects by default)",
)
@click.option(
    "--post-comment/--no-post-comment",
    default=None,
    help="Post results as MR/PR comment (auto-detects)",
)
@click.option(
    "--format",
    type=click.Choice(["console", "json", "markdown"]),
    default="markdown",
    help="Output format for comments",
)
@click.option(
    "--files",
    default="**/*.{yaml,yml,json}",
    help="File pattern to validate",
)
def ci(
    platform: str,
    post_comment: Optional[bool],
    format: str,
    files: str,
) -> None:
    """Run validation in CI/CD environment and post results to MR/PR."""
    from k8s_validator.platforms.detector import get_platform
    from pathlib import Path

    # Detect or get platform
    if platform == "auto":
        platform_adapter = get_platform()
        if not platform_adapter:
            click.echo("Could not detect CI/CD platform", err=True)
            click.echo("Set --platform manually or run 'validate' instead", err=True)
            sys.exit(1)
    else:
        platform_adapter = get_platform(platform)
        if not platform_adapter:
            click.echo(f"Platform '{platform}' not supported", err=True)
            sys.exit(1)

    # Get platform metadata
    metadata = platform_adapter.get_metadata()
    click.echo(f"Detected platform: {metadata['platform']}")

    # Get changed files from platform
    changed_files = platform_adapter.get_changed_files()

    if not changed_files:
        # Fallback to glob pattern
        changed_files = list(Path(".").glob(files))

    if not changed_files:
        click.echo("No files to validate")
        sys.exit(0)

    click.echo(f"Validating {len(changed_files)} file(s)...")

    # Create validator
    default_config = Path(".k8s-validator.yaml")
    if default_config.exists():
        validator = K8sManifestValidator.from_config_file(default_config)
    else:
        validator = K8sManifestValidator()

    # Validate
    result = validator.validate_files(changed_files)

    # Generate report
    if format == "markdown":
        reporter = MarkdownReporter()
        report_text = reporter.report(result)
    elif format == "json":
        reporter = JSONReporter()
        report_text = reporter.report(result)
    else:
        reporter = ConsoleReporter(use_color=False)
        reporter.report(result)
        report_text = ""

    # Post comment if requested (or auto-detect)
    should_post = post_comment if post_comment is not None else True

    if should_post and report_text:
        click.echo("Posting validation results as comment...")
        success = platform_adapter.post_comment(report_text)
        if success:
            click.echo("✓ Comment posted successfully")
        else:
            click.echo("✗ Failed to post comment (check permissions)", err=True)

    # Output to console as well
    if report_text:
        click.echo("\n" + report_text)

    # Exit code
    if result.has_errors:
        sys.exit(1)
    else:
        sys.exit(0)
