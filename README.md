# K8s Manifest Validator

A portable Python-based CI/CD validation tool for Kubernetes manifests including Custom Resource Definitions (CRDs).

## Features

- ✅ **YAML/JSON Syntax Validation** - Lint and parse YAML/JSON files
- ✅ **Kubernetes Schema Validation** - Validate against K8s API schemas  
- ✅ **CRD Support** - Validate custom resources with schema auto-discovery
- ✅ **Best Practices Rules** - 15+ built-in rules for security, HA, and reliability
- ✅ **Multi-Platform CI/CD** - Works with GitLab, GitHub, and Harness
- ✅ **MR/PR Comments** - Automatic feedback on merge requests
- ✅ **Multiple Output Formats** - Console, JSON, Markdown, JUnit

## Quick Start

### Installation

```bash
# Install from source
git clone https://github.com/yourusername/k8s-manifest-validator.git
cd k8s-manifest-validator
pip install -e .

# Or install from PyPI (when published)
pip install k8s-manifest-validator
```

### Basic Usage

```bash
# Validate files
k8s-validator validate deployment.yaml service.yaml

# Validate all YAML files in a directory
k8s-validator validate manifests/

# Generate configuration file
k8s-validator init

# Use custom config
k8s-validator validate --config my-config.yaml manifests/

# Output as JSON
k8s-validator validate --format json deployment.yaml

# Exit with error on any finding (strict mode)
k8s-validator validate --strict manifests/
```

### In CI/CD Pipelines

#### GitLab CI

```yaml
validate-manifests:
  stage: test
  image: python:3.11
  before_script:
    - pip install k8s-manifest-validator
  script:
    - k8s-validator validate --format markdown manifests/ > validation-report.md
  artifacts:
    reports:
      markdown: validation-report.md
```

#### GitHub Actions

Create `.github/workflows/validate-manifests.yml`:

```yaml
name: Validate K8s Manifests

on:
  pull_request:
    paths:
      - '**.yaml'
      - '**.yml'

permissions:
  contents: read
  pull-requests: write  # Required for PR comments

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install and run validator
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          pip install git+https://github.com/Moniepoint/k8s-validator.git@main
          k8s-validator ci --format markdown --post-comment
```

## Validation Rules

### Syntax Validation
- YAML parsing errors
- Invalid indentation
- Tab characters (should use spaces)
- JSON syntax errors

### Best Practices

#### Deployments/StatefulSets/DaemonSets
- ✅ Resource requests and limits defined
- ✅ Liveness and readiness probes configured
- ✅ Security context set (runAsNonRoot)
- ✅ Replica count > 1 for HA (Deployments)
- ✅ No 'latest' image tags

#### Services
- ✅ Selector matches deployment labels
- ✅ Service type explicitly set

#### Ingress/HTTPRoute
- ✅ TLS configured for production

#### ConfigMaps/Secrets
- ✅ No sensitive data in ConfigMaps
- ✅ Proper naming conventions

#### General
- ✅ Required labels present (app, version, component)
- ✅ Not using 'default' namespace
- ✅ Resource naming follows conventions

## Configuration

Create `.k8s-validator.yaml` in your project root:

```yaml
# Enable/disable validators
enable_syntax: true
enable_schema: true
enable_best_practices: true

# Kubernetes version
kubernetes_version: "1.30"

# CRD schema sources
crd_schema_sources:
  - cluster    # From kubectl
  - catalog    # Datree catalog
  - local      # Local files
  - embedded   # Pre-packaged

# Severity threshold
severity_threshold: info  # error, warning, or info

# Rule overrides
rule_overrides:
  missing-recommended-labels: false

# Exclude paths
exclude_paths:
  - .git/
  - vendor/
```

## CRD Support

The validator automatically detects and validates Custom Resource Definitions:

### Supported CRDs

- **Istio**: VirtualService, DestinationRule, Gateway, ServiceEntry
- **Argo CD**: Application, AppProject, ApplicationSet
- **Cert-Manager**: Certificate, Issuer, ClusterIssuer
- **Gateway API**: Gateway, HTTPRoute, TCPRoute, GRPCRoute
- **And more...**

### CRD Schema Sources

1. **Cluster** - Extract from current cluster via `kubectl`
2. **Catalog** - Download from [Datree CRD Catalog](https://github.com/datreeio/CRDs-catalog)
3. **Local** - Load from `.k8s-validator/crds/` directory
4. **Embedded** - Pre-packaged popular CRD schemas

## Development

```bash
# Clone repository
git clone https://github.com/yourusername/k8s-manifest-validator.git
cd k8s-manifest-validator

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linters
black .
ruff check .
mypy k8s_validator

# Type checking
mypy k8s_validator/
```

## Architecture

```
k8s_validator/
├── core/               # Core validation types and orchestrator
│   ├── models.py       # Data models
│   └── validator.py    # Main validator
├── validators/         # Validation layers
│   ├── syntax.py       # YAML/JSON validation
│   ├── schema.py       # K8s schema validation
│   └── best_practices.py # Best practices rules
├── crds/              # CRD support
│   ├── detector.py     # CRD detection
│   ├── schema_loader.py # Schema loading
│   └── cache.py        # Schema caching
├── platforms/         # CI/CD platform integrations
│   ├── gitlab.py      # GitLab integration
│   ├── github.py      # GitHub integration
│   └── harness.py     # Harness integration
├── reporters/         # Output formatters
│   ├── console.py     # Terminal output
│   ├── json.py        # JSON format
│   ├── markdown.py    # Markdown for MR/PR
│   └── junit.py       # JUnit XML
└── cli.py             # Command-line interface
```

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Credits

Built to solve real DevOps/Cloud engineering problems:
- Automated validation of K8s manifests in MRs
- Best practices enforcement before merge
- Multi-platform CI/CD support
