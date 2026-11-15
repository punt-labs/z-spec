---
paths:
  - "**/*.py"
  - "pyproject.toml"
  - "Makefile"
---

# Toolchain Standards

## PL-TC-1: Package Manager

**Statement**: Use `uv` for all package management — virtual environments, dependency
resolution, locking, building, and publishing. Never use pip, pip-tools, or poetry
directly.

**Commands**:
- `uv sync` — install dependencies from lockfile
- `uv run <cmd>` — run a command in the project's virtualenv
- `uv build` — build wheel and sdist
- `uv tool install` — install CLI tools globally

**Criterion**:
- Pass: `uv.lock` present; all commands use `uv run` or `uv` prefix
- Fail: `pip install` or `poetry` in any script or documentation

**Tooling**:
- Grep: `grep -rn "pip install\|poetry " Makefile README.md CLAUDE.md`

## PL-TC-2: Linting and Formatting

**Statement**: Use `ruff` for both linting and formatting. ruff replaces
flake8, isort, and (optionally) black. Configuration in `pyproject.toml`
under `[tool.ruff]`.

**Commands**:
- `uv run ruff check .` — lint
- `uv run ruff format --check .` — format check
- `uv run ruff format .` — auto-format

**Criterion**:
- Pass: `make lint` uses ruff; zero violations
- Fail: flake8, pylint (for lint), or isort used as primary tools

**Tooling**:
- `make lint` must exit 0

## PL-TC-3: Dual Type Checking

**Statement**: Run both `mypy --strict` and `pyright` in strict mode. Both must
pass with zero errors. They catch different classes of bugs — mypy is better at
plugin-based checks; pyright is better at type narrowing and inference.

**Configuration** (in `pyproject.toml`):
```toml
[tool.mypy]
strict = true

[tool.pyright]
typeCheckingMode = "strict"
```

**Criterion**:
- Pass: `make type` runs both mypy and pyright; both exit 0
- Fail: only one type checker configured; or errors suppressed globally

**Tooling**:
- `uv run mypy src/ tests/` and `uv run pyright src/ tests/`

## PL-TC-4: Test Framework

**Statement**: Use `pytest` for all testing. Configuration in `pyproject.toml`
under `[tool.pytest.ini_options]`. Tests live in `tests/` mirroring source
structure.

**Criterion**:
- Pass: `uv run pytest` collects and runs tests; zero failures
- Fail: unittest.TestCase as primary pattern; tests outside `tests/`

**Tooling**:
- `uv run pytest --co -q` — verify test collection
- `make test` must exit 0

## PL-TC-5: Quality Gate Composition

**Statement**: `make check` is the single gate command. It composes:
`make lint` + `make type` + `make test`. All three must pass.

**Criterion**:
- Pass: `make check` exits 0; runs lint, type, and test
- Fail: individual tool commands used instead of make check

**Tooling**:
- `make -n check` — verify all subtargets resolve

## PL-TC-6: Python Version

**Statement**: Target Python 3.13+. Use `requires-python = ">=3.13"` in
`pyproject.toml`. Use modern PEP conventions: `from __future__ import annotations`,
`X | Y` unions, `Annotated`, `type` statements.

**Criterion**:
- Pass: pyproject.toml specifies `>=3.13`; modern syntax throughout
- Fail: `requires-python` missing or targeting < 3.13
