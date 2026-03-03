"""Unit tests for best practices validator."""

from pathlib import Path

import pytest

from k8s_validator.validators.best_practices import BestPracticesValidator
from k8s_validator.core.models import Severity


@pytest.fixture
def bp_validator():
    """Create best practices validator instance."""
    return BestPracticesValidator()


def test_deployment_with_all_best_practices(bp_validator, tmp_path):
    """Test deployment that follows all best practices."""
    yaml_file = tmp_path / "good-deployment.yaml"
    yaml_file.write_text(
        """---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: good-deployment
  namespace: production
  labels:
    app: myapp
    version: "1.0"
    component: web
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
        - name: app
          image: myapp:1.0.0
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "200m"
              memory: "256Mi"
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
"""
    )

    result = bp_validator.validate_file(yaml_file)
    assert result.files_checked == 1
    # May have INFO for recommended labels, but no ERRORS
    assert result.error_count == 0


def test_deployment_missing_resources(bp_validator, tmp_path):
    """Test deployment without resource limits/requests."""
    yaml_file = tmp_path / "no-resources.yaml"
    yaml_file.write_text(
        """---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bad-deployment
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: bad
  template:
    metadata:
      labels:
        app: bad
    spec:
      containers:
        - name: app
          image: app:latest
"""
    )

    result = bp_validator.validate_file(yaml_file)
    assert result.files_checked == 1
    assert result.error_count >= 2  # Missing limits and requests

    # Check specific findings
    rule_ids = [f.rule_id for f in result.findings]
    assert "missing-resource-limits" in rule_ids
    assert "missing-resource-requests" in rule_ids


def test_deployment_low_replicas(bp_validator, tmp_path):
    """Test deployment with only 1 replica."""
    yaml_file = tmp_path / "low-replicas.yaml"
    yaml_file.write_text(
        """---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: single-replica
  namespace: production
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
        - name: app
          image: app:1.0
          resources:
            requests:
              cpu: "100m"
            limits:
              cpu: "200m"
"""
    )

    result = bp_validator.validate_file(yaml_file)
    assert result.warning_count >= 1
    assert any(f.rule_id == "low-replica-count" for f in result.findings)


def test_service_missing_selector(bp_validator, tmp_path):
    """Test service without selector."""
    yaml_file = tmp_path / "bad-service.yaml"
    yaml_file.write_text(
        """---
apiVersion: v1
kind: Service
metadata:
  name: bad-service
spec:
  ports:
    - port: 80
"""
    )

    result = bp_validator.validate_file(yaml_file)
    assert result.error_count >= 1
    assert any(f.rule_id == "missing-service-selector" for f in result.findings)


def test_configmap_with_sensitive_data(bp_validator, tmp_path):
    """Test ConfigMap with potentially sensitive data."""
    yaml_file = tmp_path / "sensitive-configmap.yaml"
    yaml_file.write_text(
        """---
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  database_password: "secret123"
  api_token: "token456"
"""
    )

    result = bp_validator.validate_file(yaml_file)
    assert result.warning_count >= 1
    assert any("sensitive" in f.message.lower() for f in result.findings)
