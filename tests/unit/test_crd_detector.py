"""Unit tests for CRD detector."""

import pytest

from k8s_validator.crds.detector import CRDDetector, BUILTIN_GROUPS


def test_detect_builtin_resource():
    """Test that built-in resources are not detected as CRDs."""
    deployment = {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "test"}}

    assert not CRDDetector.is_crd(deployment)
    assert CRDDetector.detect(deployment) is None


def test_detect_core_resource():
    """Test that core resources are not detected as CRDs."""
    pod = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": "test"}}

    assert not CRDDetector.is_crd(pod)
    assert CRDDetector.detect(pod) is None


def test_detect_istio_virtual_service():
    """Test detection of Istio VirtualService CRD."""
    vs = {
        "apiVersion": "networking.istio.io/v1beta1",
        "kind": "VirtualService",
        "metadata": {"name": "test-vs"},
    }

    assert CRDDetector.is_crd(vs)
    crd_info = CRDDetector.detect(vs)

    assert crd_info is not None
    assert crd_info.group == "networking.istio.io"
    assert crd_info.version == "v1beta1"
    assert crd_info.kind == "VirtualService"
    assert crd_info.plural == "virtualservices"


def test_detect_argocd_application():
    """Test detection of Argo CD Application CRD."""
    app = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {"name": "test-app"},
    }

    assert CRDDetector.is_crd(app)
    crd_info = CRDDetector.detect(app)

    assert crd_info is not None
    assert crd_info.group == "argoproj.io"
    assert crd_info.version == "v1alpha1"
    assert crd_info.kind == "Application"
    assert crd_info.plural == "applications"


def test_detect_gateway_api_httproute():
    """Test detection of Gateway API HTTPRoute."""
    route = {
        "apiVersion": "gateway.networking.k8s.io/v1",
        "kind": "HTTPRoute",
        "metadata": {"name": "test-route"},
    }

    assert CRDDetector.is_crd(route)
    crd_info = CRDDetector.detect(route)

    assert crd_info is not None
    assert crd_info.group == "gateway.networking.k8s.io"
    assert crd_info.version == "v1"
    assert crd_info.kind == "HTTPRoute"
    assert crd_info.plural == "httproutes"


def test_pluralization_special_cases():
    """Test special pluralization cases."""
    # Test ServiceEntry
    assert CRDDetector._pluralize("ServiceEntry") == "serviceentries"

    # Test ClusterIssuer
    assert CRDDetector._pluralize("ClusterIssuer") == "clusterissuers"

    # Test generic pluralization
    assert CRDDetector._pluralize("CustomThing") == "customthings"
