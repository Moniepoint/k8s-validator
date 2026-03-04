"""Basic tests for K8s Manifest Validator."""

from pathlib import Path


from k8s_validator.core.validator import K8sManifestValidator


def test_validator_initialization():
    """Test validator can be initialized."""
    validator = K8sManifestValidator()
    assert validator is not None
    assert validator.config is not None


def test_validate_valid_deployment():
    """Test validation of a valid deployment."""
    validator = K8sManifestValidator()
    test_file = Path("tests/fixtures/manifests/valid/deployment.yaml")

    if test_file.exists():
        result = validator.validate_file(test_file)
        # Validator counts YAML documents, not files
        assert result.files_checked >= 1
        # Should have no errors (may have warnings/info)
        assert result.error_count == 0


def test_validate_invalid_deployment():
    """Test validation of an invalid deployment."""
    validator = K8sManifestValidator()
    test_file = Path("tests/fixtures/manifests/invalid/deployment-bad.yaml")

    if test_file.exists():
        result = validator.validate_file(test_file)
        # Validator counts YAML documents, not files
        assert result.files_checked >= 1
        # Should have findings for missing resources, probes, etc.
        assert len(result.findings) > 0
