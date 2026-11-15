---
paths:
  - "**/*.py"
  - "pyproject.toml"
---

# Package Architecture Standards

Punt Labs Python packages expose three interfaces — a library, a CLI, and an
MCP server. The library is the core; CLI and MCP are thin frontends.

## PL-PA-1: Three-Interface Pattern

**Statement**: Every Python package that ships logic must expose a library API
(`__init__.py` with `__all__`), a CLI (`typer` app in `cli.py`), and an MCP
server (`FastMCP` in `server.py`). The library is the core; CLI and MCP delegate
to it.

**Exception**: Pure contract libraries (e.g., `langlearn-types`) export only
protocols and dataclasses — no CLI or MCP.

**Criterion**:
- Pass: `__init__.py` has `__all__`; `cli.py` and `server.py` import from core
- Fail: business logic in `cli.py` or `server.py`; no library API

**Tooling**:
- Grep: `grep -L "__all__" src/*/__init__.py`
- LLM review: CLI/MCP files should contain only argument parsing and delegation

## PL-PA-2: Dependency Direction

**Statement**: The dependency arrow always points inward. Core modules must never
import from CLI or MCP modules.

**Layers** (inner → outer):
1. Types/Protocols — importable with zero heavy dependencies
2. Core/Domain — business logic, data access
3. Commands — orchestration (optional, see PL-PA-3)
4. Presentation — CLI, MCP server

A module in layer N may import from layers 1..N-1, never from N+1.

**Criterion**:
- Pass: `core.py` has no `from .cli import` or `from .server import`
- Fail: core module imports from CLI, server, or commands module

**Tooling**:
- Grep: `grep -rn "from.*cli import\|from.*server import" src/*/core*`
- AST: build import graph, verify no edges from core → presentation

## PL-PA-3: Commands Layer

**Statement**: When a CLI command orchestrates multiple core calls, extract it to
a `commands/` package as a pure async function returning `CommandResult`. Use
`CommandResult(error=True, ...)` for expected user-facing failures.

**When to add**: CLI commands combine multiple core calls, manage sessions, or
format composite output. MCP tools and CLI share orchestration logic.

**When NOT to add**: Each CLI command maps 1:1 to a single core function.

**Criterion**:
- Pass: orchestration logic in `commands/`; CLI and MCP both call command functions
- Fail: orchestration duplicated between CLI and MCP

**Tooling**:
- LLM review: CLI functions > 20 lines of non-parsing logic → extract to commands
- Reference: biff `commands/` package (DES-022)

## PL-PA-4: Dependency Layering with Optional Extras

**Statement**: When a package has a heavy rendering/compute layer (GPU, image
processing) alongside a lightweight client layer, split with optional extras.
`__init__.py` must be importable without heavy extras.

**Pattern**:
```toml
dependencies = ["typer>=0.15.0,<1", "fastmcp>=3.0.0,<4"]

[project.optional-dependencies]
display = ["imgui-bundle>=1.6.0", "numpy>=2.0.0"]
```

**Criterion**:
- Pass: `import <package>` works without heavy extras installed
- Fail: top-level import fails with `ModuleNotFoundError` for optional dep

**Tooling**:
- Test: `python -c "import <package>"` in a venv without extras
- CI: `uv sync --frozen --extra dev --extra display`

## PL-PA-5: CLI Framework

**Statement**: Use `typer` + `rich` for CLI applications. Entry point registered
in `pyproject.toml` under `[project.scripts]` using the short name (not the
`punt-` PyPI prefix).

**Criterion**:
- Pass: CLI uses typer; entry point in pyproject.toml
- Fail: argparse, click directly (without typer), or sys.argv parsing

**Tooling**:
- Grep: `grep -rn "import argparse\|from click" src/`
- Check: `[project.scripts]` in pyproject.toml

## PL-PA-6: MCP Server Framework

**Statement**: Use `FastMCP` for MCP servers. Server logs to stderr only
(stdout reserved for stdio transport). Register as `<name>-server` entry point.

**Criterion**:
- Pass: `server.py` uses FastMCP; no stdout logging in server mode
- Fail: custom JSON-RPC implementation; print() in server code

**Tooling**:
- Grep: `grep -rn "print(" src/*/server.py` — zero hits
- Check: `<name>-server` in `[project.scripts]`
