# PRD: /z-spec:b-animate

## Problem

B machines need animation and model-checking to verify that operations are
executable, invariants hold across all transitions, and no deadlock states
exist. probcli supports all of this natively for B, but users need a
discoverable command with structured output --- the same UX that `/z-spec:test`
provides for Z specifications.

## Solution

A new `/z-spec:b-animate` command that runs the full probcli validation
sequence on a B machine: parse, animate, check assertions, check deadlock,
and model-check. Reports results in a structured table.

## Scope

### In Scope

- New `commands/b-animate.md` and `commands/b-animate-dev.md` skill prompts
- Full probcli validation sequence for `.mch` files
- Structured result reporting (same table format as `/z-spec:test`)
- Refinement checking when `.ref` file provided alongside `.mch`

### Out of Scope

- Z specification animation (that is `/z-spec:test`)
- Implementation verification (`.imp` files as primary target)
- Custom LTL/CTL property checking

## Success Criteria

- Runs parse, animate, CBC assertions, CBC deadlock, and model-check sequence
- Reports results in the same table format as `/z-spec:test`
- Handles `.mch`, `.ref`, and `.imp` files
- When a `.ref` file is provided, also runs refinement checking
