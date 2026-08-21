# Library and Release Guide

This guide explains exactly where each library-facing file belongs, how to validate the package in
a clean environment, and which steps must remain disabled until the intellectual-property and
license decision is complete.

## Resulting repository layout

```text
Veritas/
├── .github/workflows/ci.yml        Cross-platform tests and package build
├── docs/
│   ├── API_REFERENCE.md            Supported public API
│   ├── LIBRARY_RELEASE_GUIDE.md    This guide
│   └── index.md                    Documentation home
├── examples/library_integration.py Executable consumer example
├── src/veritas/
│   ├── __init__.py                 Top-level public exports
│   ├── api.py                      Stable pre-1.0 API facade
│   ├── py.typed                    PEP 561 typing marker
│   └── adapters/__init__.py        Internal-status documentation
├── tests/test_public_api.py        Public import and execution tests
├── CHANGELOG.md                    Version history
├── README.md                       User-facing entry point
├── mkdocs.yml                      Documentation-site configuration
└── pyproject.toml                  Package metadata and optional extras
```

Do not place `api.py` at the repository root. It belongs inside `src/veritas/` so it is included in
the Python package.

## 1. Install the development environment

### Windows PowerShell

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,docs,release]"
```

### Linux or macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,docs,release]"
```

## 2. Validate the public API

```bash
python -W error::ResourceWarning -m unittest discover -s tests -v
python examples/library_integration.py
veritas demo
veritas bench
python tools/check_portability.py
```

The example should report `ALLOW`, `CAPABILITY_ISSUED`, `COMMITTED`, and
`ledger_integrity: true`.

## 3. Build the documentation

```bash
python -m mkdocs build --strict
```

For a local preview:

```bash
python -m mkdocs serve
```

Open `http://127.0.0.1:8000`. Generated output goes to `site/`, which is ignored by Git.

## 4. Build the package

```bash
python -m build
python -m twine check dist/*
```

Expected files:

```text
dist/veritas_boundary_poc-0.1.0.tar.gz
dist/veritas_boundary_poc-0.1.0-py3-none-any.whl
```

## 5. Test outside the repository

An editable installation can hide missing package files. Test the wheel from a separate directory.

### Windows PowerShell

```powershell
py -3.13 -m venv .package-test
.\.package-test\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install .\dist\veritas_boundary_poc-0.1.0-py3-none-any.whl
Set-Location $env:TEMP
python -c "import veritas; print(veritas.__version__)"
veritas demo
veritas bench
deactivate
```

Return to the repository before continuing. Do not commit `.package-test/`, `dist/`, `build/`,
`site/`, or `*.egg-info/`.

## 6. Apply semantic versioning

| Change | Example | Version |
| --- | --- | --- |
| Backward-compatible bug or documentation fix | Close a resource leak | `0.1.1` |
| New public symbol or pre-1.0 breaking API change | Replace a factory argument | `0.2.0` |
| First declared stable API | Compatibility commitment | `1.0.0` |

For each release:

1. update `version` in `pyproject.toml`;
2. move entries from `Unreleased` in `CHANGELOG.md` to a dated version;
3. run tests, benchmark, documentation build, and package build;
4. inspect `git diff`;
5. commit the release metadata;
6. create the tag only after CI passes.

## 7. Understand the CI workflow

`.github/workflows/ci.yml` runs tests on Ubuntu, Windows, and macOS with Python 3.12 and 3.13. It
also runs the benchmark, portability and policy checks, Ruff, strict mypy, the bounded SMT check,
and package build and installation tests. It uploads build artifacts for inspection but does
**not** publish them.

## 8. Publication gate

Do not add TestPyPI or PyPI credentials and do not enable a publish workflow until all items below
are resolved:

- prior-art review completed;
- ownership checked against employment, research, and funding agreements;
- patent, trade-secret, or open-publication strategy documented;
- provisional license replaced or explicitly approved for distribution;
- package name availability confirmed;
- CI matrix green;
- clean wheel installation reproduced;
- security and limitation statements reviewed.

TestPyPI is still public distribution. Treat it as disclosure, not as a private staging system.

## 9. Future TestPyPI command

After the publication gate is approved:

```bash
python -m twine upload --repository testpypi dist/*
```

Install the test release in a fresh environment:

```bash
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  veritas-boundary-poc==0.1.0
```

Use a new version number for every upload. Published files must be treated as immutable.

## 10. Future PyPI release

After TestPyPI succeeds and the publication gate is approved, configure PyPI Trusted Publishing
from GitHub Actions instead of storing a long-lived API token. Keep publishing in a separate,
protected environment that requires manual approval.
