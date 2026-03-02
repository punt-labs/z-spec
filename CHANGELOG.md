# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
