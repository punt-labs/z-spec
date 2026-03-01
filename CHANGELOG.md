# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- **B-Method support** --- four new commands for B Abstract Machine Notation
  - `/z-spec:b-create` --- create B machines from descriptions or translate Z specs to B
  - `/z-spec:b-check` --- type-check B machines (`.mch`, `.ref`, `.imp`) with probcli
  - `/z-spec:b-animate` --- animate and model-check B machines with probcli
  - `/z-spec:b-refine` --- create or verify B refinement machines
- B notation reference (`reference/b-notation.md`) --- MACHINE/SETS/VARIABLES/INVARIANT/OPERATIONS syntax, substitution language, types, and probcli commands
- B machine patterns (`reference/b-machine-patterns.md`) --- Counter, Registry, Queue, State Machine, and Refinement patterns with complete Z-to-B translation table
- PRDs for all four B commands (`docs/prd/b-create.md`, `b-check.md`, `b-animate.md`, `b-refine.md`)
