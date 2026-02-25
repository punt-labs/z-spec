# SPARC Plan: /z partition

## S - Specification

### Problem Statement

Add a `/z partition` command that systematically derives test cases from
Z operation schemas using TTF testing tactics.

### Success Criteria

1. Command parses operation schemas from any valid Z spec
2. Applies DNF decomposition, standard partitions, and boundary analysis
3. Produces a markdown partition table per operation
4. Optional `--code` flag generates executable test code
5. Help and README updated
6. All markdown passes markdownlint

## P - Pseudocode

### Partition Algorithm (per operation)

```text
FOR each operation schema (has \Delta or \Xi):
  1. Extract: state vars, inputs(?), outputs(!), primed vars(')
  2. Extract predicate clauses from \where block
  3. Classify each clause:
     - precondition (references only unprimed state + inputs)
     - effect (references primed variables)
     - frame (x' = x)
  4. IF predicate contains \lor or \IF:
     - Split into DNF branches (each branch = separate behavior)
  5. FOR each DNF branch:
     a. Identify input/state variable domains from types + constraints
     b. Apply Standard Partition tactics:
        - Numeric in range [a,b]: {a, a+1, midpoint, b-1, b}
        - Enum: each value
        - Set: {empty, singleton, general}
        - Boolean: {ztrue, zfalse}
     c. Apply boundary analysis at each constraint edge
     d. Combine partitions (cross-product, pruned)
     e. Check feasibility: does combined predicate have contradictions?
     f. Generate concrete test values satisfying the partition
  6. Add "rejection" partitions: negate preconditions to test guards
  7. Emit partition table
```

### Output Format

```text
## Operation: AdvanceLevel

| # | Partition | Inputs | Pre-state | Expected Post-state | Notes |
|---|-----------|--------|-----------|---------------------|-------|
| 1 | Happy path | accuracy?=95 | level=5 | level'=6 | Normal advance |
| 2 | Boundary: min accuracy | accuracy?=90 | level=5 | level'=6 | At threshold |
| 3 | Boundary: max level | accuracy?=95 | level=25 | level'=26 | Advance to max |
| 4 | Boundary: both edges | accuracy?=90 | level=25 | level'=26 | Min accuracy + max pre-level |
| 5 | REJECTED: low accuracy | accuracy?=89 | level=5 | (precondition fails) | Below threshold |
| 6 | REJECTED: at max | accuracy?=95 | level=26 | (precondition fails) | Already at max |
```

## A - Architecture

### Files to Create

- `commands/partition.md` - Main skill prompt (the command implementation)

### Files to Modify

- `commands/help.md` - Add partition to command table + examples
- `README.md` - Add partition to features, commands, workflow sections

### Design Decisions

1. **No new reference files**: The partition command reuses
   `reference/z-notation.md` for Z syntax, `reference/test-patterns.md`
   for language-specific assertions, `reference/schema-patterns.md` for
   pattern recognition.
2. **No external tools**: The `allowed-tools` header will be
   `Read, Glob, Grep, Write` only. No fuzz or probcli needed - this
   is purely analytical.
3. **Code generation reuses model2code patterns**: The `--code` flag
   follows the same type mappings and test framework conventions as
   `commands/model2code.md`.

## R - Refinement

### Edge Cases

- Operations with no inputs (only state transitions) - partition on
  state variables only
- Operations with disjunction (\lor) - each disjunct becomes a
  separate behavioral branch, then partitioned independently
- Operations with implications (P \implies Q) - equivalent to
  \lnot P \lor Q, split accordingly
- Xi operations (no state change) - still partition inputs for query
  coverage
- Operations referencing global constants (axdef) - resolve constant
  values for concrete test generation

### Error Handling

- Spec file not found: same pattern as audit.md
- No operation schemas found: warn and exit
- Unbounded variables without constraints: warn, use sensible defaults

## C - Completion

### Task Breakdown

1. Create `commands/partition.md` - the skill prompt
2. Update `commands/help.md` - add to command table
3. Update `README.md` - add to features, commands, workflow
4. Run markdownlint quality gate
5. Test by reviewing output structure against a sample spec

### Definition of Done

- [ ] `commands/partition.md` exists with complete skill prompt
- [ ] Help lists the partition command
- [ ] README documents the partition command
- [ ] `npx markdownlint-cli2 "**/*.md" "#node_modules"` passes
- [ ] PRD and SPARC docs in docs/
