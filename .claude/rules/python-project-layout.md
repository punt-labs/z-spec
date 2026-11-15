---
paths:
  - "**/*.py"
  - "pyproject.toml"
---

# Project Layout Standards

## PL-PL-1: Source Layout

**Statement**: Use the `src/` layout. All package code lives under `src/<package>/`.
Tests live in `tests/` at the project root, mirroring source structure.

**Layout**:
```text
<project>/
  pyproject.toml
  uv.lock
  Makefile
  src/<package>/
    __init__.py         # Public API (__all__)
    __main__.py         # CLI entry point
    py.typed            # PEP 561 marker
    cli.py              # Typer app
    server.py           # FastMCP server
    core.py             # Core logic
    types.py            # Protocols, dataclasses, type aliases
    commands/           # (optional) Command functions
  tests/
    conftest.py
    test_*.py           # Mirror source modules
  CLAUDE.md
  CHANGELOG.md
  README.md
  .beads/
```

**Criterion**:
- Pass: code under `src/<package>/`; tests under `tests/`
- Fail: flat layout (package at repo root); tests mixed with source

**Tooling**:
- Check: `test -d src/` and `test -d tests/`

## PL-PL-2: pyproject.toml Required Sections

**Statement**: Every `pyproject.toml` must include `[project]` with name, version,
description, requires-python, authors, and license. Must include `[project.urls]`
with Homepage, Repository, and Bug Tracker. Must use hatchling build backend.

**Naming**: PyPI package uses `punt-<name>` prefix. CLI entry point uses the
short name. Python import uses underscores.

| Repo | PyPI | CLI | Import |
|------|------|-----|--------|
| quarry | `punt-quarry` | `quarry` | `quarry` |
| biff | `punt-biff` | `biff` | `biff` |
| vox | `punt-vox` | `vox` | `punt_vox` |

**Criterion**:
- Pass: all required sections present; punt- prefix on PyPI name
- Fail: missing version, description, or URLs; no punt- prefix

**Tooling**:
- `punt audit` checks pyproject.toml compliance

## PL-PL-3: Test Structure

**Statement**: Tests mirror source structure. `src/<package>/core.py` has
`tests/test_core.py`. Shared fixtures in `tests/conftest.py`. Every source
module must have a corresponding test file.

**Criterion**:
- Pass: every `src/**/*.py` has a `tests/test_*.py` counterpart
- Fail: source module with no test file

**Tooling**:
- Shell: for each `src/**/*.py`, verify `tests/test_*.py` exists
- `uv run pytest --co -q` — zero collected = fail
