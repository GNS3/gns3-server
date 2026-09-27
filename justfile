set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

_default:
    @just --list --unsorted --list-submodules

# Install the server with all optional features and dev tools
[group('dev')]
install:
    python -m pip install --upgrade pip
    python -m pip install -e '.[ai-features,dev]'

# Apply ruff autofixes for the enforced rules
[group('dev')]
format:
    python -m ruff check --fix
    python -m ruff format

# Run ruff checks (no fixes)
[group('dev')]
lint:
    python -m ruff check --exit-non-zero-on-fix
    python -m ruff format --check --diff
 
[group('dev')]
type-check:
    python -m mypy

# Run tests with coverage, e.g. `just unit tests/controller`
[group('test')]
unit *args='':
    python -m pytest --cov --cov-report=term-missing:skip-covered --cov-report=xml {{ args }}

[group('test')]
package:
    pip check

# Run all checks
[group('test')]
test: package lint type-check unit
