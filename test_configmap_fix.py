#!/usr/bin/env python3
"""Test the ConfigMap null data fix."""

from pathlib import Path
import tempfile
import sys

# Add the package to path
sys.path.insert(0, str(Path(__file__).parent))

from k8s_validator.core.validator import K8sManifestValidator

def test_configmap_with_null_data():
    """Test that ConfigMap with null data doesn't crash."""

    yaml_content = """---
apiVersion: v1
kind: ConfigMap
metadata:
  name: test-config
  namespace: default
data: null
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        f.flush()
        temp_path = Path(f.name)

    try:
        validator = K8sManifestValidator()
        result = validator.validate_file(temp_path)
        print(f"✅ Test passed! Validated file without crashing")
        print(f"   Files checked: {result.files_checked}")
        print(f"   Findings: {len(result.findings)}")
        return True
    except AttributeError as e:
        print(f"❌ Test failed with AttributeError: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed with: {type(e).__name__}: {e}")
        return False
    finally:
        temp_path.unlink()

def test_configmap_without_data():
    """Test that ConfigMap without data field doesn't crash."""

    yaml_content = """---
apiVersion: v1
kind: ConfigMap
metadata:
  name: test-config
  namespace: default
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        f.flush()
        temp_path = Path(f.name)

    try:
        validator = K8sManifestValidator()
        result = validator.validate_file(temp_path)
        print(f"✅ Test passed! Validated file without crashing")
        print(f"   Files checked: {result.files_checked}")
        print(f"   Findings: {len(result.findings)}")
        return True
    except AttributeError as e:
        print(f"❌ Test failed with AttributeError: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed with: {type(e).__name__}: {e}")
        return False
    finally:
        temp_path.unlink()

def test_configmap_with_valid_data():
    """Test that ConfigMap with valid data still works."""

    yaml_content = """---
apiVersion: v1
kind: ConfigMap
metadata:
  name: test-config
  namespace: default
data:
  app.conf: |
    setting1=value1
  password: "should_trigger_warning"
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        f.flush()
        temp_path = Path(f.name)

    try:
        validator = K8sManifestValidator()
        result = validator.validate_file(temp_path)
        print(f"✅ Test passed! Validated file with data")
        print(f"   Files checked: {result.files_checked}")
        print(f"   Findings: {len(result.findings)}")

        # Should have warning about password in key
        has_password_warning = any(
            'password' in f.message.lower()
            for f in result.findings
        )
        if has_password_warning:
            print(f"   ✅ Correctly detected sensitive data in ConfigMap key")

        return True
    except Exception as e:
        print(f"❌ Test failed with: {type(e).__name__}: {e}")
        return False
    finally:
        temp_path.unlink()

if __name__ == '__main__':
    print("Testing ConfigMap validation fix...\n")

    print("Test 1: ConfigMap with null data")
    test1 = test_configmap_with_null_data()
    print()

    print("Test 2: ConfigMap without data field")
    test2 = test_configmap_without_data()
    print()

    print("Test 3: ConfigMap with valid data")
    test3 = test_configmap_with_valid_data()
    print()

    if all([test1, test2, test3]):
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)
