"""Unit tests for syntax validator."""

from pathlib import Path

import pytest

from k8s_validator.validators.syntax import SyntaxValidator
from k8s_validator.core.models import Severity


@pytest.fixture
def syntax_validator():
    """Create syntax validator instance."""
    return SyntaxValidator()


def test_valid_yaml(syntax_validator, tmp_path):
    """Test validation of valid YAML."""
    yaml_file = tmp_path / "valid.yaml"
    yaml_file.write_text(
        """---
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  containers:
    - name: nginx
      image: nginx:1.25
"""
    )

    result = syntax_validator.validate_file(yaml_file)
    assert result.files_checked == 1
    assert result.error_count == 0


def test_invalid_yaml_syntax(syntax_validator, tmp_path):
    """Test detection of YAML syntax errors."""
    yaml_file = tmp_path / "invalid.yaml"
    yaml_file.write_text(
        """---
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
  invalid syntax here
"""
    )

    result = syntax_validator.validate_file(yaml_file)
    assert result.files_checked == 1
    assert result.error_count > 0
    assert any("parse" in f.message.lower() for f in result.findings)


def test_valid_json(syntax_validator, tmp_path):
    """Test validation of valid JSON."""
    json_file = tmp_path / "valid.json"
    json_file.write_text('{"apiVersion": "v1", "kind": "Pod"}')

    result = syntax_validator.validate_file(json_file)
    assert result.files_checked == 1
    assert result.error_count == 0


def test_invalid_json(syntax_validator, tmp_path):
    """Test detection of JSON syntax errors."""
    json_file = tmp_path / "invalid.json"
    json_file.write_text('{"apiVersion": "v1", "kind": }')

    result = syntax_validator.validate_file(json_file)
    assert result.files_checked == 1
    assert result.error_count > 0


def test_file_read_error(syntax_validator, tmp_path):
    """Test handling of unreadable files."""
    non_existent = tmp_path / "nonexistent.yaml"

    result = syntax_validator.validate_file(non_existent)
    assert result.files_checked == 1
    assert result.error_count > 0
    assert any("read" in f.message.lower() for f in result.findings)
