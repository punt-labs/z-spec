# PRD: /z-spec:b-check

## Problem

B machines (`.mch`, `.ref`, `.imp`) need type-checking before animation or
model-checking. probcli handles this natively, but users need a discoverable
command with clear error reporting and fix suggestions --- the same UX that
`/z-spec:check` provides for Z specifications with fuzz.

## Solution

A new `/z-spec:b-check` command that type-checks a B machine using probcli.
The command locates the machine file, runs `probcli Machine.mch`, interprets
the output, and reports errors with actionable fixes.

## Scope

### In Scope

- New `commands/b-check.md` and `commands/b-check-dev.md` skill prompts
- Type-checking `.mch`, `.ref`, and `.imp` files with probcli
- Error interpretation with fix suggestions
- Auto-discovery of B files in `specs/`

### Out of Scope

- Fuzz type-checking (Z only, not B)
- Refinement verification (that is `/z-spec:b-refine`)
- Animation or model-checking (that is `/z-spec:b-animate`)

## Success Criteria

- Runs `probcli Machine.mch` and reports pass/fail with parsed errors
- Suggests fixes for common B syntax and typing errors
- Auto-discovers `.mch` files in `specs/` when no argument given
