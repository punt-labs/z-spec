# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.13.0] - 2026-03-14

### Added

- **PyPI publishing** --- `release.yml` GitHub Actions workflow publishes `punt-z-spec` to PyPI on tag push via trusted publisher (build → TestPyPI → test-install → PyPI)
- **Full hybrid install.sh** --- installs uv, Python 3.13+, `punt-z-spec` CLI via `uv tool install`, registers marketplace, installs plugin, runs `z-spec doctor`; matches biff/quarry/vox install pattern

## [0.12.0] - 2026-03-14

## [0.11.0] - 2026-03-13

### Added

- **Tutorial browser** --- `browse` MCP tool loads all lessons from a manifest.toml and displays them in a paged lux view; combo-driven page switching is instant and client-side (no MCP round-trips); each page shows didactic annotations and spec tabs with section highlights auto-expanded
- **Collection manifest parser** --- `manifest.py` parses `manifest.toml` files into typed `Collection`/`Lesson` dataclasses with validation
- **`Lesson` and `Collection` types** --- frozen dataclasses in `types.py` for tutorial content with spec paths, annotations, and highlight lists

### Changed

- **Typed lux applet** --- `build_z_spec_scene` now returns a `TabBarElement` (from `punt-lux`) instead of a raw dict; all element construction uses typed dataclasses for construction-time validation and mypy/pyright coverage
- **`show_z_spec` MCP tool** --- now displays directly in lux via `LuxClient` (like vox's `show_vox`) instead of returning a scene dict; returns `{"status": "displayed"}` or `{"status": "error"}` with graceful degradation; loads all available reports (fuzz, ProB, partition, audit) and renders each as a tab
- **`check` MCP tool** --- now saves fuzz results as `<stem>.fuzz.json` alongside the .tex file
- **`punt-lux` promoted to required dependency** --- moved from optional `[lux]` extra to core dependencies

### Added

- **Fuzz tab** --- `show_z_spec` renders fuzz type-check results (pass/fail, error table with line/column/message) when a `.fuzz.json` report exists
- **Partition tab** --- `show_z_spec` renders TTF partition analysis (per-operation tables with class, branch, status, inputs, pre/post state) when a `.partition.json` report exists; summary metrics show accepted/rejected/pruned counts
- **Audit tab** --- `show_z_spec` renders test coverage audit (coverage percentage, per-category breakdown, covered constraints, uncovered constraints with suggestions) when a `.audit.json` report exists
- **`save_partition_report` MCP tool** --- validates and saves LLM-generated partition reports as `<stem>.partition.json`; called by `/z-spec:partition` skill
- **`save_audit_report` MCP tool** --- validates and saves LLM-generated audit reports as `<stem>.audit.json`; called by `/z-spec:audit` skill
- **Typed partition/audit models** --- `PartitionReport`, `OperationPartitions`, `Partition`, `AuditReport`, `AuditConstraint`, `AuditSuggestion` dataclasses in `types.py` with `to_dict()`/`from_dict()` roundtrip support

### Added

- **Python package (`punt-z-spec`)** --- CLI + MCP server hybrid following the vox pattern; deterministic L1 tools replace raw bash in skill prompts
- **CLI (`z-spec`)** --- typer CLI with `check`, `test`, `animate`, `model-check`, `report`, `doctor`, and `mcp` commands
- **MCP server (`zspec`)** --- FastMCP server with 6 tools: `check`, `test`, `animate`, `model_check`, `show_z_spec`, `get_report`; registered in plugin.json as `mcpServers.zspec`
- **LaTeX Z parser** --- extracts schemas, types, constants, and invariants from .tex files; LaTeX-to-Unicode conversion (35+ symbols); schema box rendering with open-right Unicode box-drawing
- **ProB report convention** --- `<stem>.report.json` files alongside .tex specs with ISO 8601 timestamps, all five check results, per-operation coverage, and counter-example traces; staleness detection
- **Binary wrappers** --- structured wrappers for `fuzz -t` and `probcli` with binary resolution via `$FUZZ`/`$PROBCLI` env vars, PATH, and conventional install locations
- **Lux applet** --- persistent `z-spec` frame with tabs: Spec (structure with collapsing headers), ProB (metrics/checks/coverage), Counter-Example (trace table with violation); pure scene builder with no lux dependency — callers push scenes via MCP
- **Python quality gates** --- ruff, mypy, pyright, pytest with 46 tests; added `lint-py`, `test-py`, and `report` Makefile targets

## [0.9.0] - 2026-03-09

### Added

- **Spec tab for Lux displays** --- `/z-spec:test` and `/z-spec:partition` now include a "Spec" tab that renders the Z specification as Unicode math with box-drawing schema boxes, collapsible by section; LaTeX Z commands are translated to BMP-safe Unicode symbols (ℕ, ℤ, ℙ, ∈, ⊆, ⇒, ∅, Δ, etc.)

## [0.8.0] - 2026-03-09

### Added

- **Lux visual dashboard for `/z-spec:test`** --- renders model check results (states, transitions, coverage, pass/fail) as an interactive lux dashboard when lux is available; degrades gracefully to text-only
- **Counter-example trace visualizer** --- when model checking finds a violation, displays the trace as a step-by-step table in a second lux tab with state values and violated invariant
- **Lux partition table for `/z-spec:partition`** --- renders test partition matrix as an interactive lux table with search and status filters when lux is available

## [0.2.0] - 2026-03-01

### Added

- **B-Method support** --- four new commands for B Abstract Machine Notation
  - `/z-spec:b-create` --- create B machines from descriptions or translate Z specs to B
  - `/z-spec:b-check` --- type-check B machines (`.mch`, `.ref`, `.imp`) with probcli
  - `/z-spec:b-animate` --- animate and model-check B machines with probcli
  - `/z-spec:b-refine` --- create or verify B refinement machines
- B notation reference (`reference/b-notation.md`) --- MACHINE/SETS/VARIABLES/INVARIANT/OPERATIONS syntax, substitution language, types, and probcli commands
- B machine patterns (`reference/b-machine-patterns.md`) --- Counter, Registry, Queue, State Machine, and Refinement patterns with complete Z-to-B translation table
- PRDs for all four B commands (`docs/prd/b-create.md`, `b-check.md`, `b-animate.md`, `b-refine.md`)

### Fixed

- Lean 4 product type notation: `X x Y` → `X × Y` (Unicode) in prove command, lean4-patterns reference, and z-prove PRD
- Lean 4 existential quantifier: `exists` → `∃` in type positions (lean4-patterns, z-prove PRD)
- Missing `[[lean_lib]]` section in lakefile.toml templates (prove command) --- `lake build` requires it to know what to compile
- Mathlib dependency: `version = "git#master"` → `rev = "main"` in lakefile.toml templates (Mathlib4 uses `main` branch, and `rev` is the correct TOML field)
- `omega` tactic import: noted as built-in since Lean 4.3.0, not a Mathlib dependency (lean4-patterns reference)
- Undocumented `--impl` flag: added to refine command argument list (was only referenced in error message)
- Missing `--strip` flag: added to contracts command per PRD scope (generates no-op stubs for production builds)
- Oracle PRD protocol: aligned with command's simpler flat JSON format (NDJSON, state unchanged on precondition violation)
