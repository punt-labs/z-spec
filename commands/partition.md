---
description: Derive test cases from Z specification using TTF testing tactics
argument-hint: "[spec.tex] [--code [language]] [--operation=NAME] [--json]"
allowed-tools: Read, Glob, Grep, Write
---

# /z partition - Derive Test Cases from Z Specification

Apply Test Template Framework (TTF) tactics to operation schemas
in a Z specification to produce a **complete partition table** of
test cases. Each partition represents a distinct behavioral class
that must be tested to verify the implementation conforms to the spec.

## Input

Arguments: $ARGUMENTS

Parse arguments:

- First positional argument: Z specification file (default: search `docs/*.tex`)
- `--code [language]`: Generate executable test code (auto-detect language if omitted)
- `--operation=NAME`: Partition a single operation (default: all operations)
- `--json`: Output partition data as JSON instead of markdown

## Process

### 0. Prerequisites

This command requires **no external tools**. It reads an existing
Z specification and applies testing tactics analytically. The specification
should already exist and have been type-checked (via `/z check`).

### 1. Locate the Specification

If a file path is provided, use it directly.

If no file specified:

- Look in `docs/` for `.tex` files containing Z specifications
- If multiple found, ask user to specify

Read the specification file.

### 2. Extract Operation Schemas

Scan the specification for operation schemas. An operation schema is
any schema containing `\Delta` or `\Xi`:

```latex
\begin{schema}{OperationName}
\Delta State \\        % or \Xi State
input? : Type \\       % inputs (optional)
output! : Type         % outputs (optional)
\where
% predicates
\end{schema}
```

For each operation, extract:

- **Name**: The schema name
- **Kind**: `\Delta` (state-changing) or `\Xi` (query)
- **State schema**: The referenced state schema name
- **Inputs**: Variables ending in `?` with their types
- **Outputs**: Variables ending in `!` with their types
- **Predicates**: All clauses in the `\where` block

If `--operation=NAME` is specified, process only that operation.

### 3. Resolve Context

Before partitioning, resolve the context each operation needs:

#### 3a. State Variables

Read the state schema to get all state variables and their types.
Read the invariant predicates from the state schema's `\where` block.

#### 3b. Global Constants

Scan `\begin{axdef}` blocks for constants referenced in the operation
predicates. Resolve their concrete values.

#### 3c. Free Types

Scan `\begin{zed}` blocks for free type definitions referenced
in the operation. Record all constructors.

### 4. Classify Predicates

For each predicate clause in the operation's `\where` block,
classify it:

| Classification | Rule | Example |
|----------------|------|---------|
| **Precondition** | References only unprimed state vars and/or inputs | `level < 26` |
| **Effect** | References primed variables (`x'`) | `level' = level + 1` |
| **Frame** | Has form `x' = x` (no change) | `attempts' = attempts` |
| **Input constraint** | Constrains only input variables | `accuracy? \geq 90` |
| **Output definition** | Defines output in terms of state/inputs | `result! = balance` |

### 5. Apply TTF Testing Tactics

For each operation, apply three tactics in sequence:

#### Tactic 1: DNF Decomposition

If the predicate contains disjunction (`\lor`) or conditionals
(`\IF ... \THEN ... \ELSE`), decompose into Disjunctive Normal Form.
Each disjunct becomes a separate **behavioral branch**.

Example:

```latex
% Original (TryWithdraw)
(amount? \leq balance \land balance' = balance - amount? \land success! = ztrue)
\lor
(amount? > balance \land balance' = balance \land success! = zfalse)
```

Produces two branches:

- Branch 1: Successful withdrawal (`amount? <= balance`)
- Branch 2: Failed withdrawal (`amount? > balance`)

If the predicate has no disjunction, the operation has a single branch.

**Handle implications**: `P \implies Q` is equivalent to
`\lnot P \lor Q`. Decompose accordingly.

#### Tactic 2: Standard Partitions

For each input and relevant state variable in each branch,
apply type-based standard partitions:

| Variable Type | Standard Partitions |
|---------------|---------------------|
| `\nat` with `x \geq a` and `x \leq b` | `{a, a+1, (a+b) div 2, b-1, b}` |
| `\nat` with only lower bound `x \geq a` | `{a, a+1, a+10}` |
| `\nat_1` (positive natural) | `{1, 2, 10}` |
| `\nat` (unconstrained) | `{0, 1, 5}` |
| Free type `T ::= c1 \| c2 \| ...` | Each constructor: `{c1, c2, ...}` |
| `ZBOOL` | `{ztrue, zfalse}` |
| `\power X` (set) | `{\emptyset, \{x\}, \{x, y\}}` |
| `\seq X` (sequence) | `{\langle\rangle, \langle x \rangle, \langle x, y \rangle}` |
| Given set `[X]` | Use symbolic names: `{x1, x2, x3}` |

#### Tactic 3: Boundary Analysis

For each constraint involving a comparison, generate test values
at and around the boundary:

| Constraint | Boundary Values (respecting the type domain) |
|------------|-----------------------------------------------|
| `x \geq N` | Values just below, at, and just above `N` (for example `{N-1, N, N+1}`), clamped to the domain of `x` (for `\nat`, replace any negative value such as `N-1 < 0` by `0`, or treat it explicitly as a *type-violation* test). |
| `x \leq N` | Values just below, at, and just above `N` (for example `{N-1, N, N+1}`), again only where these lie in the domain of `x`; otherwise clamp to the nearest in-domain value or mark as a *type-violation* test. |
| `x > N` | Values at and just above `N` (for example `{N, N+1}`), adjusted so that they remain within the domain of `x` (or explicitly tagged as *type-violation* tests if they do not). |
| `x < N` | Values just below and at `N` (for example `{N-1, N}`), using only those that are in the domain of `x`; if `N-1` would be out of domain (such as `-1` for `\nat`), clamp or treat the case as a *type-violation* test. |
| `x = N` | Values just below, at, and just above `N` (for example `{N-1, N, N+1}`), with the same requirement to clamp to the domain of `x` or to classify any out-of-domain values as *type-violation* tests. |
| `x \in A \upto B` | Values just outside and inside the interval (for example `{A-1, A, A+1, B-1, B, B+1}`), but only where these are in the domain of `x`; otherwise clamp `A-1`/`B+1` to the nearest in-domain value or mark such cases as *type-violation* tests rather than ordinary precondition failures. |
| `x \in \dom f` | member, non-member |
| `x \notin S` | member (predicate violated / rejected), non-member (predicate satisfied / accepted) |

> Note: When applying these patterns to concrete Z types (such as `\nat`), always ensure that generated boundary values lie within the type’s domain. Values outside the domain should either be clamped to the nearest in-domain value or clearly identified as separate *type-violation* test cases, not as standard boundary/precondition tests.
### 6. Generate Partitions

Combine the tactics to produce concrete partitions:

#### 6a. Accepted Partitions

For each behavioral branch, cross the standard partitions of all
inputs and relevant state variables, keeping only combinations that
satisfy the branch predicate. For each feasible combination:

1. Choose concrete input values from the standard partition
2. Choose a concrete pre-state satisfying the state invariant
3. Compute the expected post-state by applying the effects
4. Record any expected outputs

#### 6b. Rejected Partitions

For each precondition, generate a partition where that precondition
is violated (negated) while other preconditions hold. These test
that the implementation correctly rejects invalid inputs.

- If the operation has precondition `P1 \land P2 \land P3`, generate:
  - `\lnot P1 \land P2 \land P3`
  - `P1 \land \lnot P2 \land P3`
  - `P1 \land P2 \land \lnot P3`

For each rejected partition, record:

- The concrete input values that violate the precondition
- The pre-state
- The expected behavior: "precondition fails" (operation should not execute)

#### 6c. Invariant Preservation Partitions

For each state schema invariant, generate at least one partition
that exercises the invariant's boundary after an operation:

- If invariant is `level \leq 26` and operation increments level,
  include a partition where `level = 25` and the operation runs
  (testing that `level' = 26` still satisfies the invariant)

#### 6d. Prune Infeasible Partitions

Remove any partition where the combined predicates are contradictory.
Common contradictions:

- `x < 5 \land x > 10` (empty range)
- `x \in \emptyset` (impossible membership)
- Pre-state violates the state invariant

Mark pruned partitions with a note explaining why they were removed.

### 7. Format Output

#### Markdown Output (default)

For each operation, produce:

```markdown
## Operation: OperationName

**Kind**: Delta (state-changing)
**Inputs**: input1? : Type1, input2? : Type2
**Pre-state variables**: var1, var2, var3
**Preconditions**: P1, P2
**Effects**: E1, E2

### Behavioral Branches

1. **Branch 1**: Description (when condition holds)
2. **Branch 2**: Description (when condition fails)

### Partition Table

| # | Class | Branch | Inputs | Pre-state | Post-state | Notes |
|---|-------|--------|--------|-----------|------------|-------|
| 1 | Happy path | 1 | in1=V1 | s1=V2 | s1'=V3 | Normal case |
| 2 | Boundary: min input | 1 | in1=MIN | s1=V2 | s1'=V3 | At lower bound |
| 3 | Boundary: max state | 1 | in1=V1 | s1=MAX-1 | s1'=MAX | Near invariant limit |
| 4 | REJECTED: bad input | - | in1=BAD | s1=V2 | (no change) | Precondition: P1 fails |
| 5 | PRUNED | - | - | - | - | Infeasible: P1 contradicts P2 |

### Summary

- **Total partitions**: N
- **Accepted**: A (test that operation works correctly)
- **Rejected**: R (test that guards prevent invalid transitions)
- **Pruned**: P (infeasible, no test needed)
- **Coverage**: A + R test cases needed for full conformance
```

#### JSON Output (--json flag)

```json
{
  "specification": "docs/example.tex",
  "operations": [
    {
      "name": "OperationName",
      "kind": "delta",
      "inputs": [{"name": "input1", "type": "nat", "constraints": ["input1 >= 0"]}],
      "stateVars": ["var1", "var2"],
      "branches": [
        {"id": 1, "description": "Success case", "condition": "amount <= balance"}
      ],
      "partitions": [
        {
          "id": 1,
          "class": "happy-path",
          "branch": 1,
          "status": "accepted",
          "inputs": {"input1": 50},
          "preState": {"var1": 100},
          "postState": {"var1": 150},
          "notes": "Normal case"
        },
        {
          "id": 4,
          "class": "rejected",
          "status": "rejected",
          "inputs": {"input1": -1},
          "preState": {"var1": 100},
          "postState": null,
          "notes": "Precondition: input1 >= 0 fails"
        }
      ],
      "summary": {
        "total": 5,
        "accepted": 3,
        "rejected": 1,
        "pruned": 1
      }
    }
  ]
}
```

### 8. Generate Test Code (--code flag)

If `--code` is specified, generate executable test code.

#### 8a. Detect Target Language

If language specified after `--code`, use it.

Otherwise auto-detect from project files (same logic as `model2code`):

| File Present | Language |
|--------------|----------|
| `Package.swift`, `*.xcodeproj` | Swift |
| `package.json`, `tsconfig.json` | TypeScript |
| `pyproject.toml`, `setup.py`, `requirements.txt` | Python |
| `build.gradle.kts`, `pom.xml` | Kotlin |

#### 8b. Generate Test Cases

For each accepted and rejected partition, generate a test case
using the language's test framework. Consult `reference/test-patterns.md`
for assertion patterns.

**Test naming convention**: `test_<Operation>_<PartitionClass>_<Number>`

Example (Python/pytest):

```python
class TestAdvanceLevel:

    def test_happy_path_normal_advance(self):
        """Partition 1: accuracy=95, level=5 -> level'=6"""
        state = State(level=5, attempts=10, correct=8)
        state.advance_level(accuracy=95)
        assert state.level == 6
        assert state.attempts == 10  # frame: unchanged

    def test_boundary_min_accuracy(self):
        """Partition 2: accuracy=90 (threshold), level=5 -> level'=6"""
        state = State(level=5, attempts=10, correct=8)
        state.advance_level(accuracy=90)
        assert state.level == 6

    def test_boundary_max_level(self):
        """Partition 3: accuracy=95, level=25 -> level'=26"""
        state = State(level=25, attempts=10, correct=8)
        state.advance_level(accuracy=95)
        assert state.level == 26

    def test_rejected_low_accuracy(self):
        """Partition 5: accuracy=89 (below threshold) -> no change"""
        state = State(level=5, attempts=10, correct=8)
        # Operation should not change observable state for rejected inputs
        state.advance_level(accuracy=89)
        assert state.level == 5  # unchanged

    def test_rejected_at_max_level(self):
        """Partition 6: level=26 (at max) -> no change"""
        state = State(level=26, attempts=10, correct=8)
        state.advance_level(accuracy=95)
        assert state.level == 26  # unchanged
```

Example (Swift/XCTest):

```swift
final class AdvanceLevelTests: XCTestCase {

    // Partition 1: Happy path - normal advance
    func testHappyPath_normalAdvance() {
        var state = State(level: 5, attempts: 10, correct: 8)
        state.advanceLevel(accuracy: 95)
        XCTAssertEqual(state.level, 6)
        XCTAssertEqual(state.attempts, 10) // frame: unchanged
    }

    // Partition 2: Boundary - minimum accuracy
    func testBoundary_minAccuracy() {
        var state = State(level: 5, attempts: 10, correct: 8)
        state.advanceLevel(accuracy: 90)
        XCTAssertEqual(state.level, 6)
    }

    // Partition 5: Rejected - accuracy below threshold
    func testRejected_lowAccuracy() {
        var state = State(level: 5, attempts: 10, correct: 8)
        // Operation should not execute
        state.advanceLevel(accuracy: 89)
        XCTAssertEqual(state.level, 5) // unchanged
    }
}
```

Example (TypeScript/Jest):

```typescript
describe('AdvanceLevel', () => {

  // Partition 1: Happy path - normal advance
  it('advances level with sufficient accuracy', () => {
    const state = createState({ level: 5, attempts: 10, correct: 8 });
    advanceLevel(state, { accuracy: 95 });
    expect(state.level).toBe(6);
    expect(state.attempts).toBe(10); // frame: unchanged
  });

  // Partition 2: Boundary - minimum accuracy
  it('advances at exactly 90% accuracy threshold', () => {
    const state = createState({ level: 5, attempts: 10, correct: 8 });
    advanceLevel(state, { accuracy: 90 });
    expect(state.level).toBe(6);
  });

  // Partition 5: Rejected - accuracy below threshold
  it('does not advance with accuracy below 90%', () => {
    const state = createState({ level: 5, attempts: 10, correct: 8 });
    expect(() => advanceLevel(state, { accuracy: 89 })).toThrow();
  });
});
```

Example (Kotlin/JUnit 5):

```kotlin
class AdvanceLevelTest {

    // Partition 1: Happy path - normal advance
    @Test
    fun `advances level with sufficient accuracy`() {
        val state = State(level = 5, attempts = 10, correct = 8)
        state.advanceLevel(accuracy = 95)
        assertEquals(6, state.level)
        assertEquals(10, state.attempts) // frame: unchanged
    }

    // Partition 5: Rejected - accuracy below threshold
    @Test
    fun `does not advance with accuracy below 90`() {
        val state = State(level = 5, attempts = 10, correct = 8)
        assertThrows<PreconditionError> {
            state.advanceLevel(accuracy = 89)
        }
    }
}
```

#### 8c. Write Test File

Write the generated tests to a file following project conventions:

- Swift: `<Name>PartitionTests.swift` in the test target directory
- TypeScript: `<name>.partition.test.ts` alongside existing tests
- Python: `test_<name>_partition.py` in the test directory
- Kotlin: `<Name>PartitionTest.kt` in the test source directory

**Do not overwrite existing test files.** Use the `Partition` suffix
to distinguish from hand-written or model2code-generated tests.

### 9. Report Summary

After generating all partitions, report a summary:

```markdown
## Partition Summary

**Specification**: docs/example.tex
**Operations analyzed**: 5

| Operation | Accepted | Rejected | Pruned | Total |
|-----------|----------|----------|--------|-------|
| Deposit | 4 | 2 | 0 | 6 |
| Withdraw | 5 | 3 | 1 | 9 |
| Transfer | 8 | 4 | 2 | 14 |
| GetBalance | 2 | 0 | 0 | 2 |
| CloseAccount | 3 | 2 | 0 | 5 |
| **Total** | **22** | **11** | **3** | **36** |

**33 test cases needed for full spec-implementation conformance.**
```

If `--code` was used, also report:

```markdown
**Generated**: test_account_partition.py (33 test cases)
```

## Integration with Other Commands

### With /z audit

After running `/z partition`, the user can run `/z audit` to check
how many of the derived partitions already have test coverage.
The partition table provides the "what should be tested" checklist;
audit checks "what is actually tested."

### With /z model2code

`/z model2code` generates starter tests using intuitive enumeration.
`/z partition` generates systematic tests using formal partitioning.
The two complement each other: model2code for quick scaffolding,
partition for complete conformance verification.

## Error Handling

| Error | Response |
|-------|----------|
| Specification not found | "No Z specification found. Specify path or create one with `/z code2model`." |
| No operation schemas | "No operation schemas found (schemas with `\Delta` or `\Xi`). Nothing to partition." |
| Parse error in schema | "Could not parse schema {name}. Skipping." (continue with others) |
| Unsupported language for --code | "Language not supported for code generation. Supported: Swift, TypeScript, Python, Kotlin. Showing partition table only." |
| No constraints on input | "Warning: {input} has no explicit bounds. Using default partition values." |

## Reference

- Z notation syntax: `reference/z-notation.md`
- Schema patterns: `reference/schema-patterns.md`
- Test assertion patterns: `reference/test-patterns.md`
- probcli guide: `reference/probcli-guide.md`
