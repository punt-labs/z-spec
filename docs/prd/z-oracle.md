# PRD: /z-spec:oracle

## Problem

Partition-derived tests (from `/z-spec:partition`) cover structurally
identified cases but cannot cover all input combinations. Hand-written
tests reflect the developer's assumptions, not the spec's semantics.
Random testing without a reference implementation has no way to know
what the correct answer should be.

This is the **oracle problem**: property-based testing can generate
thousands of random inputs, but without an independent source of truth,
there is nothing to compare the implementation's output against.

The `/z-spec:prove` command already generates an executable Lean 4 model
of the specification. That model encodes the exact semantics of every
operation. It can serve as a test oracle -- an independent, spec-derived
reference implementation that answers "what should happen?" for any input.

## Solution

A new `/z-spec:oracle` command that generates a property-based test
harness using the Lean 4 model (from `/z-spec:prove`) as a test oracle.
The harness runs random operation sequences through both the Lean model
and the real implementation, applying an abstraction function to compare
states after each step.

For each specification, the command generates:

- **Lean executable oracle** -- a `main` function that reads JSON
  commands from stdin and writes state as JSON to stdout
- **Abstraction function scaffold** -- maps concrete implementation
  state to the abstract Z state schema for comparison
- **Property-based test driver** -- uses the target language's PBT
  library (fast-check, Hypothesis, SwiftCheck, kotest)
- **Random operation generators** -- produce valid operation sequences
  respecting input types and preconditions

## Scope

### In Scope

- New `commands/oracle.md` skill prompt
- Lean 4 oracle executable generation (JSON stdin/stdout protocol)
- Abstraction function scaffolds for Swift, TypeScript, Python, Kotlin
- PBT driver generation using idiomatic libraries per language
- Operation sequence generators with precondition filtering
- State comparison via abstraction function after each operation
- Shrinking support for failing sequences
- Updates to `commands/help.md` and `README.md`

### Out of Scope

- Automated abstraction function inference
- Stateful model-based testing (Erlang QuickCheck style)
- Performance benchmarking of oracle vs. implementation
- Lean model optimizations for execution speed
- Changes to existing commands beyond help updates

## Oracle Protocol

The Lean executable communicates via newline-delimited JSON (NDJSON)
over stdin/stdout:

```json
// Input (one command per line)
{"op": "Deposit", "args": {"amount": 50}}
{"op": "Withdraw", "args": {"amount": 30}}

// Output (state after each command — flat state object)
{"balance": 50, "status": "active"}
{"balance": 20, "status": "active"}
```

On startup, the oracle outputs the initial state before reading any
commands. If an operation's precondition is not met, the oracle
outputs the state unchanged (no mutation).

## User Workflow

```text
/z-spec:code2model     -> create spec from code
/z-spec:check          -> verify spec is well-typed
/z-spec:test           -> verify spec is internally consistent
/z-spec:prove          -> generate Lean 4 model + proofs
/z-spec:partition      -> derive structured test cases
/z-spec:oracle         -> generate PBT harness with Lean oracle   <-- NEW
/z-spec:audit          -> verify tests exist in codebase
```

The oracle command depends on `/z-spec:prove` output. It extends the
Lean project with an executable oracle target and generates the test
harness alongside the implementation's existing test suite.

## Success Criteria

- Generated Lean oracle compiles via `lake build` and executes
  operation sequences from JSON input
- Generated test driver runs at least 1000 random operation sequences
- Abstraction function scaffold compiles in the target language
- State divergence between oracle and implementation is detected
  and reported with the minimal shrunk operation sequence
- Precondition violations in the oracle match precondition violations
  in the implementation (no false positives from invalid inputs)
- The harness runs as part of the normal test suite with no manual
  setup beyond `lake build` for the oracle binary
