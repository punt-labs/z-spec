# PRD: /z partition

## Problem

The z-spec plugin can verify a Z specification is internally consistent
(via probcli model-checking) and can check whether existing tests cover
spec constraints (via `/z audit`). However, neither tool systematically
derives the **minimal complete set of test cases** needed to prove that
an implementation conforms to the specification.

This is the spec-implementation conformance gap: the spec is verified,
the code exists, but nothing guarantees the code actually follows the spec.

## Solution

A new `/z partition` command that applies Test Template Framework (TTF)
tactics to each operation schema in a Z specification, producing:

1. A **partition table** (markdown) listing every distinct test class
   per operation, with concrete input values and expected outcomes.
2. Optionally, **executable test code** in the target language.

The command uses no external tools beyond what the plugin already
requires. Claude reads the spec and applies the TTF algorithm directly.

## TTF Tactics Applied

For each operation schema, the command:

1. **Extracts the predicate** (preconditions + effects + frame conditions)
2. **Applies Disjunctive Normal Form (DNF)** decomposition to split
   disjunctions into separate cases
3. **Applies Standard Partitions (SP)** for each input/state variable:
   - Numeric: zero, one, boundary, interior, above-boundary
   - Set: empty, singleton, general
   - Sequence: empty, singleton, general
   - Enum: each value
4. **Applies boundary analysis** at constraint edges
   (e.g., `x >= 90` produces tests at 89, 90, 91)
5. **Prunes infeasible partitions** where predicates contradict
6. **Generates concrete test values** satisfying each partition

## Scope

### In Scope

- New `commands/partition.md` skill prompt
- Partition table output (markdown, default)
- Optional `--code` flag to generate executable test code
- Language auto-detection (reuses model2code's detection)
- Integration point: partition output feeds into `/z audit` for
  coverage tracking
- Updates to `commands/help.md` and `README.md`

### Out of Scope

- No external tool dependencies (no Fastest, no Java, no Prolog)
- No changes to existing commands
- No new reference files (reuses existing reference/*.md)
- No CI integration (future work)

## User Workflow

```text
/z code2model     -> create spec from code
/z check          -> verify spec is well-typed
/z test           -> verify spec is internally consistent
/z partition      -> derive required test cases from spec  <-- NEW
/z audit          -> verify those tests exist in codebase
```

## Success Criteria

- For any operation schema with bounded inputs, `/z partition` produces
  a partition table covering all distinct behavioral cases
- Generated test values satisfy the partition predicates
- Infeasible partitions are identified and excluded
- The output is actionable: a developer can write tests directly from
  the table without needing to understand TTF theory
