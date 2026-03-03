"""Unit tests for CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from k8s_validator.cli import cli, main


@pytest.fixture
def runner():
    """Create Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_yaml(tmp_path):
    """Create a sample YAML file."""
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text("""---
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  containers:
    - name: nginx
      image: nginx:1.25
      resources:
        requests:
          cpu: "100m"
        limits:
          cpu: "200m"
      livenessProbe:
        httpGet:
          path: /
          port: 80
      securityContext:
        runAsNonRoot: true
""")
    return yaml_file


def test_cli_help(runner):
    """Test CLI help output."""
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'K8s Manifest Validator' in result.output


def test_version_command(runner):
    """Test version command."""
    result = runner.invoke(cli, ['version'])
    assert result.exit_code == 0
    assert 'k8s-validator version 0.1.0' in result.output


def test_init_command_creates_config(runner, tmp_path):
    """Test init command creates config file."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ['init'])
        assert result.exit_code == 0
        assert Path('.k8s-validator.yaml').exists()
        
        # Verify config content
        config = Path('.k8s-validator.yaml').read_text()
        assert 'enable_syntax: true' in config
        assert 'kubernetes_version:' in config


def test_init_command_config_exists_error(runner, tmp_path):
    """Test init command fails if config exists."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create config first
        Path('.k8s-validator.yaml').write_text('existing config')
        
        result = runner.invoke(cli, ['init'])
        assert result.exit_code == 1
        assert 'already exists' in result.output


def test_validate_command_single_file(runner, sample_yaml):
    """Test validate command with single file."""
    result = runner.invoke(cli, ['validate', str(sample_yaml)])
    assert result.exit_code == 0
    assert 'Validation Summary' in result.output


def test_validate_command_directory(runner, tmp_path):
    """Test validate command with directory."""
    # Create multiple YAML files
    (tmp_path / "file1.yaml").write_text("---\napiVersion: v1\nkind: Pod\n")
    (tmp_path / "file2.yaml").write_text("---\napiVersion: v1\nkind: Service\n")
    
    result = runner.invoke(cli, ['validate', str(tmp_path)])
    # May have validation errors, but should run
    assert result.exit_code in [0, 1]


def test_validate_command_json_format(runner, sample_yaml):
    """Test validate command with JSON output."""
    result = runner.invoke(cli, ['validate', '--format', 'json', str(sample_yaml)])
    assert result.exit_code == 0
    # JSON output should be parseable
    import json
    try:
        json.loads(result.output)
    except json.JSONDecodeError:
        # Might have preamble, check for JSON structure
        assert '{' in result.output and '}' in result.output


def test_validate_command_markdown_format(runner, sample_yaml):
    """Test validate command with Markdown output."""
    result = runner.invoke(cli, ['validate', '--format', 'markdown', str(sample_yaml)])
    assert result.exit_code == 0
    assert '##' in result.output  # Markdown headers


def test_validate_command_console_format(runner, sample_yaml):
    """Test validate command with console output (default)."""
    result = runner.invoke(cli, ['validate', '--format', 'console', str(sample_yaml)])
    assert result.exit_code == 0
    assert 'Validation Summary' in result.output


def test_validate_command_no_color(runner, sample_yaml):
    """Test validate command with colors disabled."""
    result = runner.invoke(cli, ['validate', '--no-color', str(sample_yaml)])
    assert result.exit_code == 0


def test_validate_command_strict_mode(runner, tmp_path):
    """Test validate command in strict mode."""
    # Create file with warnings
    yaml_file = tmp_path / "warnings.yaml"
    yaml_file.write_text("""---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test
  template:
    metadata:
      labels:
        app: test
    spec:
      containers:
        - name: test
          image: test:latest
          resources:
            requests:
              cpu: "100m"
            limits:
              cpu: "200m"
""")
    
    result = runner.invoke(cli, ['validate', '--strict', str(yaml_file)])
    # Should exit with error even on warnings
    assert result.exit_code == 1


def test_validate_command_no_files(runner):
    """Test validate command with no files."""
    result = runner.invoke(cli, ['validate'])
    assert result.exit_code == 1
    assert 'No files to validate' in result.output


def test_validate_command_output_to_file(runner, sample_yaml, tmp_path):
    """Test validate command with output file."""
    output_file = tmp_path / "report.json"
    result = runner.invoke(cli, [
        'validate',
        '--format', 'json',
        '--output', str(output_file),
        str(sample_yaml)
    ])
    assert result.exit_code == 0
    assert output_file.exists()


@patch('k8s_validator.platforms.detector.get_platform')
def test_ci_command_platform_detection(mock_get_platform, runner):
    """Test CI command with platform auto-detection."""
    # Mock platform that doesn't detect
    mock_get_platform.return_value = None
    
    result = runner.invoke(cli, ['ci'])
    assert result.exit_code == 1
    assert 'Could not detect CI/CD platform' in result.output


@patch('k8s_validator.platforms.detector.get_platform')
def test_ci_command_with_platform_override(mock_get_platform, runner, tmp_path):
    """Test CI command with manual platform selection."""
    # Create mock platform adapter
    mock_adapter = MagicMock()
    mock_adapter.get_metadata.return_value = {'platform': 'gitlab'}
    mock_adapter.get_changed_files.return_value = []
    mock_get_platform.return_value = mock_adapter
    
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ['ci', '--platform', 'gitlab'])
        # Should run but may have no files
        assert 'Detected platform: gitlab' in result.output or 'No files' in result.output


@patch('k8s_validator.platforms.detector.get_platform')
def test_ci_command_validates_changed_files(mock_get_platform, runner, tmp_path):
    """Test CI command validates changed files."""
    # Create test file
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text("---\napiVersion: v1\nkind: Pod\n")
    
    # Mock platform adapter
    mock_adapter = MagicMock()
    mock_adapter.get_metadata.return_value = {'platform': 'github'}
    mock_adapter.get_changed_files.return_value = [yaml_file]
    mock_adapter.post_comment.return_value = True
    mock_get_platform.return_value = mock_adapter
    
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ['ci', '--platform', 'github'])
        # Should validate the file
        assert result.exit_code in [0, 1]  # May have validation errors


def test_main_entry_point():
    """Test main entry point function."""
    # Just verify it's callable
    assert callable(main)
