---
description: Verify code refines Z specification via abstraction function and commutativity checks
argument-hint: "[spec.tex] [language: swift|typescript|python|kotlin] [--lean] [--generate-abstraction] [--impl file]"
allowed-tools: Bash(which:*), Bash(fuzz:*), Bash(lean:*), Bash(lake:*), Read, Glob, Grep, Write
---

# /z-spec:refine - Data Refinement Verification

Verify that implementation code correctly refines a Z specification
by defining an **abstraction function** and generating **commutativity
tests** (and optionally Lean 4 proofs) for every operation.

The key correctness property for each operation:

```
abstract(concreteOp(concreteState)) = abstractOp(abstract(concreteState))
```

If this holds for every operation, the code is a provably correct
refinement of the specification.

## Input

Arguments: $ARGUMENTS

Parse arguments:

- First positional argument: Z specification file (default: search `docs/*.tex`)
- Second positional argument: target language (default: auto-detect)
- `--lean` - also generate Lean 4 commutativity proofs in `proofs/`
- `--generate-abstraction` - auto-generate abstraction function scaffold
  (otherwise walk the user through defining it interactively)
- `--impl <file>` - path to implementation file (default: auto-detect from project)

## Process

### 0. Prerequisites

Verify the specification has been type-checked:

```bash
which fuzz >/dev/null 2>&1 || echo "FUZZ_NOT_FOUND"
```

**If fuzz is not found**: Warn but do not block. The refinement
process can proceed without type-checking, but recommend running
`/z-spec:check` first.

If `--lean` is specified, verify Lean 4 and Lake are installed:

```bash
which lean >/dev/null 2>&1 || echo "LEAN_NOT_FOUND"
which lake >/dev/null 2>&1 || echo "LAKE_NOT_FOUND"
```

**If lean or lake not found**: Stop and tell the user:
> Lean 4 is not installed. Run `/z-spec:setup lean` to install
> the Lean 4 toolchain via elan. Or omit `--lean` to generate
> commutativity tests only.

The Z specification should already exist. Implementation code
should also exist (from `/z-spec:model2code` or hand-written).

### 1. Locate the Specification

If a file path is provided, use it directly.

If no file specified:

- Look in `docs/` for `.tex` files containing Z specifications
- If multiple found, ask user to specify

Read the specification file.

### 2. Parse the Specification

Scan the specification and extract the following constructs.

#### 2a. Given Sets

Look for given set declarations in `\begin{zed}` blocks:

```latex
\begin{zed}
[USERID, SESSIONID]
\end{zed}
```

Record each name. These are abstract types in the specification.

#### 2b. Free Types

Look for free type definitions in `\begin{zed}` blocks:

```latex
\begin{zed}
Status ::= pending | active | suspended | closed
\end{zed}
```

Record the type name and all constructors.

#### 2c. Axiomatic Definitions

Look for `\begin{axdef}` blocks with global constants:

```latex
\begin{axdef}
MAX\_BALANCE : \nat
\where
MAX\_BALANCE = 1000000
\end{axdef}
```

Record each constant name, type, and defining predicate.

#### 2d. State Schema (Abstract State)

Look for state schemas -- schemas that are **not** operations
(no `\Delta`, `\Xi`, or primed-only variables):

```latex
\begin{schema}{Account}
balance : \num \\
status : Status
\where
balance \geq 0 \lor status = suspended \\
status = closed \implies balance = 0
\end{schema}
```

Record:

- **Name**: The schema name (this is the abstract state type)
- **Fields**: Each variable name and its Z type
- **Invariants**: All predicates in the `\where` block

#### 2e. Init Schema

Look for schemas that initialize the state:

```latex
\begin{schema}{InitAccount}
Account'
\where
balance' = 0 \\
status' = pending
\end{schema}
```

Record:

- **Name**: The schema name
- **Target state**: The referenced state schema
- **Initial values**: Assignments to primed variables

#### 2f. Operation Schemas

Look for schemas containing `\Delta` or `\Xi`:

```latex
\begin{schema}{Deposit}
\Delta Account \\
amount? : \nat_1
\where
status = active \\
balance' = balance + amount? \\
status' = status
\end{schema}
```

For each operation, record:

- **Name**: The schema name
- **Kind**: `\Delta` (state-changing) or `\Xi` (query/observation)
- **State schema**: The referenced state schema name
- **Inputs**: Variables ending in `?` with their types
- **Outputs**: Variables ending in `!` with their types
- **Preconditions**: Predicates referencing only unprimed state
  variables and/or inputs
- **Effects**: Predicates referencing primed variables (`x'`)
- **Frame conditions**: Predicates of the form `x' = x`

### 3. Detect Target Language and Locate Implementation

#### 3a. Detect Language

If a language is specified, use it.

Otherwise auto-detect from project files:

| File Present | Language |
|--------------|----------|
| `Package.swift`, `*.xcodeproj` | Swift |
| `package.json`, `tsconfig.json` | TypeScript |
| `pyproject.toml`, `setup.py`, `requirements.txt` | Python |
| `build.gradle.kts`, `pom.xml` | Kotlin |

#### 3b. Locate Implementation Code

Search for classes or structs matching the state schema name:

- Swift: Look for `struct <Name>` or `class <Name>` in `Sources/`
  or `src/`
- TypeScript: Look for `interface <Name>` or `class <Name>` in
  `src/` or `lib/`
- Python: Look for `class <Name>` in `src/` or the project root
- Kotlin: Look for `data class <Name>` or `class <Name>` in
  `src/main/`

If not found, ask the user to specify the implementation file path.

#### 3c. Extract Concrete State

Read the implementation file and extract:

- **Concrete state type**: The class/struct name and its fields
- **Concrete operations**: Methods corresponding to Z operations
- **Concrete init**: Constructor or factory method

Build a mapping table:

```markdown
| Abstract (Z spec) | Concrete (code) | Notes |
|--------------------|-----------------|-------|
| balance : Nat | balance: number | Direct mapping |
| status : Status | statusCode: string | Needs translation |
| - | lastModified: Date | Implementation detail (no abstract counterpart) |
```

### 4. Generate Abstraction Function Scaffold (--generate-abstraction)

If `--generate-abstraction` is specified, analyze both the abstract
spec and the concrete code to produce a starter abstraction function.

#### 4a. Field Matching Heuristics

For each abstract state variable, attempt to find a matching
concrete field using these heuristics:

| Heuristic | Example |
|-----------|---------|
| Exact name match | `balance` -> `balance` |
| Case-insensitive match | `Status` -> `status` |
| Prefix/suffix match | `balance` -> `accountBalance`, `balanceAmount` |
| Type-compatible match | `Nat` -> `number`, `Int`, `int` |

For fields that cannot be auto-matched, emit a `TODO` comment.

#### 4b. Enum/Free Type Mapping

For each Z free type used in the abstract state, detect how
the concrete code represents it and generate a mapping function:

```typescript
/**
 * Maps concrete status code to abstract Status type.
 *
 * Abstract: Status ::= pending | active | suspended | closed
 * Concrete: string codes "P", "A", "S", "C"
 *
 * VERIFY: confirm these mappings match your code conventions.
 */
function mapStatusCode(code: string): Status {
  const mapping: Record<string, Status> = {
    'P': Status.Pending,
    'A': Status.Active,
    'S': Status.Suspended,
    'C': Status.Closed,
  };
  const result = mapping[code];
  if (result === undefined) {
    throw new Error(`Unknown status code: ${code}`);
  }
  return result;
}
```

If the concrete code uses an enum that directly matches the Z
free type (same constructors, possibly different casing), generate
a direct mapping comment instead.

#### 4c. Generate the Abstraction Function

Produce the function combining all field mappings:

**TypeScript:**

```typescript
/**
 * Abstraction function: maps concrete state to abstract Z spec state.
 *
 * Abstract state (from Z spec):
 *   balance : Nat
 *   status : Status (pending | active | suspended | closed)
 *
 * Concrete state (from code):
 *   balance: number
 *   statusCode: string  // "P", "A", "S", "C"
 *   lastModified: Date
 *
 * YOU MUST VERIFY AND CUSTOMIZE THIS FUNCTION.
 */
export function abstract(concrete: ConcreteAccount): AbstractAccount {
  return {
    balance: concrete.balance,
    status: mapStatusCode(concrete.statusCode),
    // NOTE: lastModified has no abstract counterpart (implementation detail)
  };
}
```

**Swift:**

```swift
/// Abstraction function: maps concrete state to abstract Z spec state.
///
/// Abstract state (from Z spec):
///   balance : Nat
///   status : Status
///
/// Concrete state (from code):
///   balance: Int
///   statusCode: String
///   lastModified: Date
///
/// YOU MUST VERIFY AND CUSTOMIZE THIS FUNCTION.
func abstract(_ concrete: ConcreteAccount) -> AbstractAccount {
    AbstractAccount(
        balance: concrete.balance,
        status: mapStatusCode(concrete.statusCode)
        // NOTE: lastModified has no abstract counterpart
    )
}
```

**Python:**

```python
def abstract(concrete: ConcreteAccount) -> AbstractAccount:
    """
    Abstraction function: maps concrete state to abstract Z spec state.

    Abstract state (from Z spec):
        balance : Nat
        status : Status (pending | active | suspended | closed)

    Concrete state (from code):
        balance: int
        status_code: str  # "P", "A", "S", "C"
        last_modified: datetime

    YOU MUST VERIFY AND CUSTOMIZE THIS FUNCTION.
    """
    return AbstractAccount(
        balance=concrete.balance,
        status=map_status_code(concrete.status_code),
        # NOTE: last_modified has no abstract counterpart
    )
```

**Kotlin:**

```kotlin
/**
 * Abstraction function: maps concrete state to abstract Z spec state.
 *
 * Abstract state (from Z spec):
 *   balance : Nat
 *   status : Status (pending | active | suspended | closed)
 *
 * Concrete state (from code):
 *   balance: Int
 *   statusCode: String
 *   lastModified: Instant
 *
 * YOU MUST VERIFY AND CUSTOMIZE THIS FUNCTION.
 */
fun abstract(concrete: ConcreteAccount): AbstractAccount =
    AbstractAccount(
        balance = concrete.balance,
        status = mapStatusCode(concrete.statusCode),
        // NOTE: lastModified has no abstract counterpart
    )
```

Mark every mapping with a comment indicating:

- `// Direct mapping` -- same name, compatible type
- `// Translated mapping -- VERIFY` -- type or name differs
- `// TODO: no matching concrete field found` -- needs manual work
- `// NOTE: no abstract counterpart (implementation detail)` --
  concrete field with no Z equivalent

### 5. Guided Abstraction Function (interactive, no --generate-abstraction)

If the user does not specify `--generate-abstraction`, walk them
through defining the abstraction function interactively.

#### 5a. Show Abstract State

Display the abstract state extracted from the Z specification:

```markdown
## Abstract State (from Z spec)

| Variable | Type | Invariant constraints |
|----------|------|-----------------------|
| balance | Nat | balance >= 0 OR status = suspended |
| status | Status | status = closed IMPLIES balance = 0 |
```

#### 5b. Show Concrete State

Display the concrete state extracted from the implementation:

```markdown
## Concrete State (from code)

| Field | Type | Default |
|-------|------|---------|
| balance | number | 0 |
| statusCode | string | "P" |
| lastModified | Date | new Date() |
```

#### 5c. Prompt for Each Mapping

For each abstract variable, ask the user:

1. "Which concrete field(s) map to `balance : Nat`?"
2. "Is a transformation needed? (e.g., type conversion, scaling)"

For each Z free type, ask:

3. "How does your code represent `Status ::= pending | active
   | suspended | closed`? (enum, string codes, numeric constants)"
4. "What are the concrete values for each constructor?"

For concrete fields with no obvious abstract counterpart, ask:

5. "`lastModified: Date` has no apparent Z counterpart. Is this
   an implementation detail to ignore, or does it correspond to
   an abstract variable I missed?"

#### 5d. Generate from Responses

After collecting all mappings, generate the abstraction function
using the same patterns as step 4c.

### 6. Generate Abstract Operation Functions

Before generating commutativity tests, ensure abstract operation
functions exist. These mirror the Z spec semantics:

**TypeScript:**

```typescript
/**
 * Abstract Deposit operation (from Z spec).
 * Precondition: status = active
 * Effect: balance' = balance + amount
 * Frame: status' = status
 */
function abstractDeposit(
  state: AbstractAccount,
  input: { amount: number }
): AbstractAccount {
  return {
    balance: state.balance + input.amount,
    status: state.status,
  };
}

function depositPrecondition(
  state: AbstractAccount,
  amount: number
): boolean {
  return state.status === Status.Active && amount > 0;
}
```

Generate one abstract operation function per Z operation schema.
These serve as the specification oracle for commutativity tests.

### 7. Generate Init Commutativity Test

Verify that the initial concrete state abstracts to the initial
abstract state. This is the base case for refinement correctness.

**TypeScript:**

```typescript
describe('Refinement: Init', () => {
  it('concrete init abstracts to abstract init', () => {
    // Concrete initialization
    const concrete = new ConcreteAccount();

    // Abstract initialization
    const abstractInit: AbstractAccount = {
      balance: 0,
      status: Status.Pending,
    };

    // Verify: abstract(init_concrete) = init_abstract
    expect(abstract(concrete)).toEqual(abstractInit);
  });
});
```

**Swift:**

```swift
final class RefinementInitTests: XCTestCase {

    // Init commutativity: abstract(init_concrete) = init_abstract
    func testConcreteInitAbstractsToAbstractInit() {
        let concrete = ConcreteAccount()
        let abstractInit = AbstractAccount(balance: 0, status: .pending)
        XCTAssertEqual(abstract(concrete), abstractInit)
    }
}
```

**Python:**

```python
class TestRefinementInit:

    def test_concrete_init_abstracts_to_abstract_init(self):
        """Init commutativity: abstract(init_concrete) = init_abstract"""
        concrete = ConcreteAccount()
        abstract_init = AbstractAccount(balance=0, status=Status.PENDING)
        assert abstract(concrete) == abstract_init
```

**Kotlin:**

```kotlin
class RefinementInitTest {

    @Test
    fun `concrete init abstracts to abstract init`() {
        val concrete = ConcreteAccount()
        val abstractInit = AbstractAccount(balance = 0, status = Status.Pending)
        assertEquals(abstractInit, abstract(concrete))
    }
}
```

### 8. Generate Commutativity Tests

For each Delta operation, generate tests verifying:

```
abstract(concreteOp(concreteState)) = abstractOp(abstract(concreteState))
```

For each Xi operation, generate tests verifying:

```
concreteQuery(concreteState) = abstractQuery(abstract(concreteState))
```

#### 8a. Example-Based Commutativity Tests

For each operation, generate concrete test cases using values
from the partition table (if `/z-spec:partition` has been run)
or representative values from the type domain.

**TypeScript:**

```typescript
describe('Refinement: Deposit', () => {
  it('concrete deposit commutes with abstract deposit', () => {
    // Setup concrete state
    const concrete = createConcreteState({
      balance: 100,
      statusCode: 'A',
    });

    // Capture abstract before
    const abstractBefore = abstract(concrete);

    // Run concrete operation
    concreteDeposit(concrete, { amount: 50 });

    // Run abstract operation on the abstract-before state
    const abstractAfter = abstractDeposit(abstractBefore, {
      amount: 50,
    });

    // Verify commutativity: abstract . concrete = abstract . abstract
    expect(abstract(concrete)).toEqual(abstractAfter);
  });

  it('commutes at boundary: zero balance', () => {
    const concrete = createConcreteState({
      balance: 0,
      statusCode: 'A',
    });
    const abstractBefore = abstract(concrete);
    concreteDeposit(concrete, { amount: 1 });
    const abstractAfter = abstractDeposit(abstractBefore, {
      amount: 1,
    });
    expect(abstract(concrete)).toEqual(abstractAfter);
  });

  it('commutes at boundary: large amount', () => {
    const concrete = createConcreteState({
      balance: 500,
      statusCode: 'A',
    });
    const abstractBefore = abstract(concrete);
    concreteDeposit(concrete, { amount: 999500 });
    const abstractAfter = abstractDeposit(abstractBefore, {
      amount: 999500,
    });
    expect(abstract(concrete)).toEqual(abstractAfter);
  });
});
```

**Swift:**

```swift
final class RefinementDepositTests: XCTestCase {

    func testDeposit_commutesWithAbstractDeposit() {
        var concrete = ConcreteAccount(balance: 100, statusCode: "A")
        let abstractBefore = abstract(concrete)
        concrete.deposit(amount: 50)
        let abstractAfter = abstractDeposit(abstractBefore, amount: 50)
        XCTAssertEqual(abstract(concrete), abstractAfter)
    }

    func testDeposit_commutesAtBoundary_zeroBalance() {
        var concrete = ConcreteAccount(balance: 0, statusCode: "A")
        let abstractBefore = abstract(concrete)
        concrete.deposit(amount: 1)
        let abstractAfter = abstractDeposit(abstractBefore, amount: 1)
        XCTAssertEqual(abstract(concrete), abstractAfter)
    }
}
```

**Python:**

```python
class TestRefinementDeposit:

    def test_deposit_commutes_with_abstract_deposit(self):
        """Commutativity: abstract(deposit(c)) = absDeposit(abstract(c))"""
        concrete = ConcreteAccount(balance=100, status_code="A")
        abstract_before = abstract(concrete)
        concrete.deposit(amount=50)
        abstract_after = abstract_deposit(abstract_before, amount=50)
        assert abstract(concrete) == abstract_after

    def test_deposit_commutes_at_boundary_zero_balance(self):
        """Commutativity at boundary: balance=0"""
        concrete = ConcreteAccount(balance=0, status_code="A")
        abstract_before = abstract(concrete)
        concrete.deposit(amount=1)
        abstract_after = abstract_deposit(abstract_before, amount=1)
        assert abstract(concrete) == abstract_after
```

**Kotlin:**

```kotlin
class RefinementDepositTest {

    @Test
    fun `deposit commutes with abstract deposit`() {
        val concrete = ConcreteAccount(balance = 100, statusCode = "A")
        val abstractBefore = abstract(concrete)
        concrete.deposit(amount = 50)
        val abstractAfter = abstractDeposit(abstractBefore, amount = 50)
        assertEquals(abstractAfter, abstract(concrete))
    }

    @Test
    fun `deposit commutes at boundary - zero balance`() {
        val concrete = ConcreteAccount(balance = 0, statusCode = "A")
        val abstractBefore = abstract(concrete)
        concrete.deposit(amount = 1)
        val abstractAfter = abstractDeposit(abstractBefore, amount = 1)
        assertEquals(abstractAfter, abstract(concrete))
    }
}
```

#### 8b. Property-Based Commutativity Tests

For each operation, also generate a property-based test using
the language's property testing library. This provides much
stronger coverage than example-based tests alone.

**TypeScript (fast-check):**

```typescript
import fc from 'fast-check';

describe('Refinement: Deposit (property-based)', () => {
  it('commutes for all valid inputs', () => {
    fc.assert(
      fc.property(
        validConcreteStateArb,
        fc.integer({ min: 1, max: 1000000 }),
        (concreteState, amount) => {
          const absBefore = abstract(concreteState);
          // Only test when precondition holds
          fc.pre(depositPrecondition(absBefore, amount));

          const concreteCopy = structuredClone(concreteState);
          concreteDeposit(concreteCopy, { amount });
          const absAfter = abstractDeposit(absBefore, { amount });

          expect(abstract(concreteCopy)).toEqual(absAfter);
        },
      ),
    );
  });
});
```

**Swift (SwiftCheck or custom):**

```swift
func testDeposit_commutesForAllValidInputs() {
    // Property-based: test with random valid states and amounts
    for _ in 0..<100 {
        let balance = Int.random(in: 0...1000000)
        let amount = Int.random(in: 1...100000)
        var concrete = ConcreteAccount(balance: balance, statusCode: "A")
        let abstractBefore = abstract(concrete)

        guard depositPrecondition(abstractBefore, amount: amount) else {
            continue
        }

        concrete.deposit(amount: amount)
        let abstractAfter = abstractDeposit(abstractBefore, amount: amount)
        XCTAssertEqual(abstract(concrete), abstractAfter,
            "Failed for balance=\(balance), amount=\(amount)")
    }
}
```

**Python (Hypothesis):**

```python
from hypothesis import given, assume
import hypothesis.strategies as st

class TestRefinementDepositProperty:

    @given(
        balance=st.integers(min_value=0, max_value=1000000),
        amount=st.integers(min_value=1, max_value=1000000),
    )
    def test_deposit_commutes_for_all_valid_inputs(
        self, balance: int, amount: int
    ):
        concrete = ConcreteAccount(balance=balance, status_code="A")
        abstract_before = abstract(concrete)
        assume(deposit_precondition(abstract_before, amount))

        concrete.deposit(amount=amount)
        abstract_after = abstract_deposit(abstract_before, amount=amount)
        assert abstract(concrete) == abstract_after
```

**Kotlin (kotest-property):**

```kotlin
class RefinementDepositPropertyTest : FunSpec({
    test("deposit commutes for all valid inputs") {
        checkAll(
            Arb.int(0..1_000_000),
            Arb.int(1..1_000_000),
        ) { balance, amount ->
            val concrete = ConcreteAccount(balance = balance, statusCode = "A")
            val abstractBefore = abstract(concrete)
            assume(depositPrecondition(abstractBefore, amount))

            concrete.deposit(amount = amount)
            val abstractAfter = abstractDeposit(abstractBefore, amount = amount)
            abstract(concrete) shouldBe abstractAfter
        }
    }
})
```

#### 8c. Test Values Selection

When generating example-based tests, select values that exercise:

| Category | Strategy |
|----------|----------|
| Happy path | Typical mid-range values |
| Boundary: lower | Minimum valid input/state values |
| Boundary: upper | Maximum or near-maximum values |
| Boundary: invariant | Values near invariant limits |
| Multiple operations | Compose two operations and check |

Use partition data from `/z-spec:partition` if available.

### 9. Generate Lean Proofs (--lean flag)

If `--lean` is specified and `proofs/` exists, generate formal
commutativity proofs in addition to tests.

#### 9a. Check or Create Lean Project

If `proofs/` exists with `lakefile.toml`, reuse it. Otherwise
create the project structure (same as `/z-spec:prove`).

#### 9b. Generate Abstraction Function in Lean

Define the abstraction function as a Lean function mapping
concrete state to abstract state:

```lean
/-
  ZSpec.Refinement
  Generated from: <spec-file-name>

  Abstraction function and commutativity proofs for data refinement.
-/

import ZSpec.State
import ZSpec.Operations

-- Concrete state (mirrors implementation)
structure ConcreteAccount where
  balance : Nat
  statusCode : String
  lastModified : Nat  -- simplified from Date
  deriving Repr

-- Abstraction function
def abstract (c : ConcreteAccount) : Account := {
  balance := c.balance,
  status := mapStatusCode c.statusCode
}

-- Status code mapping
def mapStatusCode (code : String) : Status :=
  match code with
  | "P" => Status.pending
  | "A" => Status.active
  | "S" => Status.suspended
  | "C" => Status.closed
  | _   => Status.pending  -- fallback
```

#### 9c. Generate Concrete Operations in Lean

Mirror the implementation's operations in Lean:

```lean
-- Concrete deposit (mirrors implementation)
def concreteDeposit (c : ConcreteAccount) (amount : Nat) :
    ConcreteAccount :=
  { c with balance := c.balance + amount }

-- Concrete init
def concreteInit : ConcreteAccount :=
  { balance := 0, statusCode := "P", lastModified := 0 }
```

#### 9d. Generate Init Commutativity Theorem

```lean
/-- Init commutativity: abstract(init_concrete) = init_abstract -/
theorem init_commutes :
    abstract concreteInit = initAccount := by
  sorry
```

#### 9e. Generate Operation Commutativity Theorems

For each Delta operation:

```lean
/-- Deposit commutativity:
    abstract(concreteDeposit c amount) = deposit (abstract c) amount -/
theorem deposit_commutes (c : ConcreteAccount) (amount : Nat)
    (h_pre : deposit_precondition (abstract c) amount) :
    abstract (concreteDeposit c amount) =
      deposit (abstract c) amount := by
  sorry
```

For each Xi operation:

```lean
/-- GetBalance commutativity:
    concreteGetBalance c = getBalance (abstract c) -/
theorem getBalance_commutes (c : ConcreteAccount) :
    concreteGetBalance c = getBalance (abstract c) := by
  sorry
```

#### 9f. Attempt Proof Discharge

Try the following tactics in order for each `sorry`:

| Tactic | When It Works |
|--------|---------------|
| `rfl` | When both sides reduce to the same term |
| `simp [abstract, concreteOp, abstractOp]` | Definition unfolding |
| `unfold abstract concreteOp abstractOp; rfl` | Direct unfolding |
| `unfold abstract concreteOp abstractOp; simp` | Unfolding with simplification |
| `unfold abstract concreteOp abstractOp; omega` | Arithmetic after unfolding |
| `ext <;> simp [abstract, concreteOp, abstractOp]` | Structure extensionality |
| `aesop` | Automated reasoning (Mathlib, slower) |

Follow the same batch discharge process as `/z-spec:prove`:

1. First pass: try `rfl` and `simp` for all obligations
2. Build once, check which succeeded
3. Second pass: try `unfold; omega` for remaining
4. Build again
5. Final pass: try `ext` or `aesop` for remaining
6. Final build

```bash
cd proofs && timeout 120 lake build 2>&1
```

#### 9g. File Structure

Generate these files in the existing `proofs/` project:

```
proofs/
  ZSpec/
    Refinement/
      Concrete.lean         -- Concrete state and operations
      Abstraction.lean      -- Abstraction function
      Commutativity.lean    -- Commutativity theorems
```

### 10. Write Test File

Write the generated commutativity tests to a file following
project conventions:

| Language | File Name | Location |
|----------|-----------|----------|
| Swift | `<Name>RefinementTests.swift` | Test target directory |
| TypeScript | `<name>.refinement.test.ts` | Alongside existing tests |
| Python | `test_<name>_refinement.py` | Test directory |
| Kotlin | `<Name>RefinementTest.kt` | Test source directory |

**Do not overwrite existing test files.** Use the `Refinement`
suffix to distinguish from hand-written, model2code-generated,
or partition-generated tests.

Write the abstraction function and abstract operation functions
to a separate file:

| Language | File Name |
|----------|-----------|
| Swift | `<Name>Abstraction.swift` |
| TypeScript | `<name>.abstraction.ts` |
| Python | `<name>_abstraction.py` |
| Kotlin | `<Name>Abstraction.kt` |

### 11. Report Results

After generating all artifacts, report a summary.

#### 11a. Abstraction Function Summary

```markdown
## Abstraction Function

**Abstract state**: Account (balance, status)
**Concrete state**: ConcreteAccount (balance, statusCode, lastModified)

| Abstract Field | Concrete Field | Mapping |
|----------------|----------------|---------|
| balance : Nat | balance: number | Direct (identity) |
| status : Status | statusCode: string | Translated via mapStatusCode |
| - | lastModified: Date | Ignored (implementation detail) |
```

#### 11b. Commutativity Test Table

```markdown
## Commutativity Tests

**Specification**: docs/account.tex
**Implementation**: src/account.ts
**Test file**: src/account.refinement.test.ts

| # | Operation | Kind | Example tests | Property tests | Status |
|---|-----------|------|---------------|----------------|--------|
| 1 | Init | init | 1 | - | generated |
| 2 | Deposit | Delta | 3 | 1 | generated |
| 3 | Withdraw | Delta | 4 | 1 | generated |
| 4 | GetBalance | Xi | 2 | 1 | generated |
| 5 | CloseAccount | Delta | 2 | 1 | generated |

### Summary

- **Operations covered**: 5
- **Example-based tests**: 12
- **Property-based tests**: 4
- **Total test cases**: 16
```

#### 11c. Lean Proof Status (if --lean)

```markdown
## Lean Commutativity Proofs

**Lean project**: proofs/

| # | Theorem | Status | Tactic |
|---|---------|--------|--------|
| 1 | init_commutes | proved | rfl |
| 2 | deposit_commutes | sorry | - |
| 3 | withdraw_commutes | proved | simp; omega |
| 4 | getBalance_commutes | proved | rfl |
| 5 | closeAccount_commutes | sorry | - |

### Summary

- **Total obligations**: 5
- **Proved**: 3
- **Remaining (sorry)**: 2
- **Proof coverage**: 60%
```

#### 11d. Next Steps

Suggest concrete next steps based on the results:

- "The abstraction function is the critical piece. **Review it
  manually** to confirm every mapping is correct. An incorrect
  abstraction function will cause tests to pass even when the
  implementation is wrong."
- "Run the commutativity tests: `npm test` / `swift test` /
  `pytest` / `gradle test`"
- If any tests fail: "A failing commutativity test means either
  (1) the abstraction function is wrong, (2) the implementation
  diverges from the spec, or (3) the abstract operation function
  has a bug. Check the abstraction function first."
- If `--lean` was used with remaining `sorry` markers: "To
  discharge remaining proofs, open `proofs/ZSpec/Refinement/
  Commutativity.lean` in VS Code with the Lean 4 extension."
- "For stronger coverage, run `/z-spec:partition` to derive
  systematic test inputs, then use those values in the
  commutativity tests."

### 12. File Update Policy

When re-running refinement for a specification that already
has refinement artifacts:

- **Never overwrite** the abstraction function file if it exists.
  The user may have customized it. Instead, generate a `.new`
  file and show a diff.
- **Append new tests** for operations added to the spec.
- **Comment out stale tests** for operations removed from the
  spec (do not delete).
- **Never overwrite** Lean proofs that have had `sorry` replaced
  with real proofs. Check each theorem: if the body is not
  `sorry`, preserve it.

## Error Handling

| Error | Response |
|-------|----------|
| Specification not found | "No Z specification found. Specify path or create one with `/z-spec:code2model`." |
| No state schemas | "No state schemas found in the specification. Cannot define refinement without abstract state." |
| No operation schemas | "No operation schemas found. Generating only init commutativity test." |
| Implementation not found | "Could not locate implementation code for {StateName}. Specify the file path: `/z-spec:refine spec.tex typescript --impl src/account.ts`" |
| Language not detected | "Could not detect target language. Specify explicitly: `/z-spec:refine spec.tex typescript`" |
| Lean not installed (with --lean) | "Lean 4 is not installed. Run `/z-spec:setup lean` to install via elan, or omit `--lean`." |
| Lake not installed (with --lean) | "Lake not found. It should be included with Lean 4. Run `elan toolchain install leanprover/lean4:v4.16.0`." |
| `lake build` fails | Show errors, suggest fixes, keep `sorry` markers. |
| `lake build` timeout | "Build timed out after 120s. Try `cd proofs && lake build` manually." |
| Parse error in schema | "Could not parse schema {name}. Skipping." (continue with others) |
| No matching concrete field | "Could not match abstract field `{field}` to any concrete field. Mark as TODO in abstraction function." |
| Abstraction file already exists | "Abstraction function file already exists. Generating `{name}.abstraction.new.ts` for comparison." |
| Property testing library not found | "Property testing library not found. Install `fast-check` / `hypothesis` / `SwiftCheck` / `kotest-property`. Generating example-based tests only." |

## Worked Example

Given this Z specification (`docs/account.tex`):

```latex
\begin{zed}
Status ::= pending | active | suspended | closed
\end{zed}

\begin{schema}{Account}
balance : \nat \\
status : Status
\where
balance \geq 0 \\
status = closed \implies balance = 0
\end{schema}

\begin{schema}{InitAccount}
Account'
\where
balance' = 0 \\
status' = pending
\end{schema}

\begin{schema}{Deposit}
\Delta Account \\
amount? : \nat_1
\where
status = active \\
balance' = balance + amount? \\
status' = status
\end{schema}

\begin{schema}{Withdraw}
\Delta Account \\
amount? : \nat_1
\where
status = active \\
amount? \leq balance \\
balance' = balance - amount? \\
status' = status
\end{schema}

\begin{schema}{GetBalance}
\Xi Account \\
result! : \nat
\where
result! = balance
\end{schema}
```

And this implementation (`src/account.ts`):

```typescript
export enum StatusCode {
  Pending = 'P',
  Active = 'A',
  Suspended = 'S',
  Closed = 'C',
}

export class BankAccount {
  balance: number;
  statusCode: StatusCode;
  lastModified: Date;

  constructor() {
    this.balance = 0;
    this.statusCode = StatusCode.Pending;
    this.lastModified = new Date();
  }

  deposit(amount: number): void {
    if (amount <= 0) throw new Error('Amount must be positive');
    if (this.statusCode !== StatusCode.Active) return;
    this.balance += amount;
    this.lastModified = new Date();
  }

  withdraw(amount: number): void {
    if (amount <= 0) throw new Error('Amount must be positive');
    if (this.statusCode !== StatusCode.Active) return;
    if (amount > this.balance) return;
    this.balance -= amount;
    this.lastModified = new Date();
  }

  getBalance(): number {
    return this.balance;
  }
}
```

Running `/z-spec:refine docs/account.tex typescript --generate-abstraction`
produces:

**src/account.abstraction.ts:**

```typescript
import { BankAccount, StatusCode } from './account';

// --- Abstract types (from Z spec) ---

export enum Status {
  Pending = 'pending',
  Active = 'active',
  Suspended = 'suspended',
  Closed = 'closed',
}

export interface AbstractAccount {
  balance: number;
  status: Status;
}

// --- Status code mapping ---

function mapStatusCode(code: StatusCode): Status {
  const mapping: Record<StatusCode, Status> = {
    [StatusCode.Pending]: Status.Pending,
    [StatusCode.Active]: Status.Active,
    [StatusCode.Suspended]: Status.Suspended,
    [StatusCode.Closed]: Status.Closed,
  };
  return mapping[code];
}

// --- Abstraction function ---

/**
 * Maps concrete BankAccount to abstract Account from Z spec.
 *
 * Abstract state: balance : Nat, status : Status
 * Concrete state: balance, statusCode, lastModified
 *
 * VERIFY: confirm all mappings are correct.
 */
export function abstract(concrete: BankAccount): AbstractAccount {
  return {
    balance: concrete.balance, // Direct mapping
    status: mapStatusCode(concrete.statusCode), // Translated
    // NOTE: lastModified has no abstract counterpart
  };
}

// --- Abstract operations (from Z spec) ---

export function abstractInit(): AbstractAccount {
  return { balance: 0, status: Status.Pending };
}

export function depositPrecondition(
  state: AbstractAccount,
  amount: number,
): boolean {
  return state.status === Status.Active && amount > 0;
}

export function abstractDeposit(
  state: AbstractAccount,
  amount: number,
): AbstractAccount {
  return { balance: state.balance + amount, status: state.status };
}

export function withdrawPrecondition(
  state: AbstractAccount,
  amount: number,
): boolean {
  return (
    state.status === Status.Active &&
    amount > 0 &&
    amount <= state.balance
  );
}

export function abstractWithdraw(
  state: AbstractAccount,
  amount: number,
): AbstractAccount {
  return { balance: state.balance - amount, status: state.status };
}

export function abstractGetBalance(state: AbstractAccount): number {
  return state.balance;
}
```

**src/account.refinement.test.ts:**

```typescript
import { BankAccount, StatusCode } from './account';
import {
  abstract,
  abstractInit,
  abstractDeposit,
  abstractWithdraw,
  abstractGetBalance,
  depositPrecondition,
  withdrawPrecondition,
} from './account.abstraction';
import fc from 'fast-check';

function createAccount(
  balance: number,
  statusCode: StatusCode,
): BankAccount {
  const acct = new BankAccount();
  acct.balance = balance;
  acct.statusCode = statusCode;
  return acct;
}

// --- Init commutativity ---

describe('Refinement: Init', () => {
  it('concrete init abstracts to abstract init', () => {
    const concrete = new BankAccount();
    expect(abstract(concrete)).toEqual(abstractInit());
  });
});

// --- Deposit commutativity ---

describe('Refinement: Deposit', () => {
  it('commutes for typical deposit', () => {
    const concrete = createAccount(100, StatusCode.Active);
    const absBefore = abstract(concrete);
    concrete.deposit(50);
    expect(abstract(concrete)).toEqual(abstractDeposit(absBefore, 50));
  });

  it('commutes at boundary: zero balance', () => {
    const concrete = createAccount(0, StatusCode.Active);
    const absBefore = abstract(concrete);
    concrete.deposit(1);
    expect(abstract(concrete)).toEqual(abstractDeposit(absBefore, 1));
  });

  it('commutes at boundary: minimum amount', () => {
    const concrete = createAccount(500, StatusCode.Active);
    const absBefore = abstract(concrete);
    concrete.deposit(1);
    expect(abstract(concrete)).toEqual(abstractDeposit(absBefore, 1));
  });

  it('commutes for all valid inputs (property)', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 1000000 }),
        fc.integer({ min: 1, max: 1000000 }),
        (balance, amount) => {
          const concrete = createAccount(balance, StatusCode.Active);
          const absBefore = abstract(concrete);
          fc.pre(depositPrecondition(absBefore, amount));
          concrete.deposit(amount);
          const absAfter = abstractDeposit(absBefore, amount);
          expect(abstract(concrete)).toEqual(absAfter);
        },
      ),
    );
  });
});

// --- Withdraw commutativity ---

describe('Refinement: Withdraw', () => {
  it('commutes for typical withdrawal', () => {
    const concrete = createAccount(200, StatusCode.Active);
    const absBefore = abstract(concrete);
    concrete.withdraw(50);
    expect(abstract(concrete)).toEqual(
      abstractWithdraw(absBefore, 50),
    );
  });

  it('commutes at boundary: withdraw entire balance', () => {
    const concrete = createAccount(100, StatusCode.Active);
    const absBefore = abstract(concrete);
    concrete.withdraw(100);
    expect(abstract(concrete)).toEqual(
      abstractWithdraw(absBefore, 100),
    );
  });

  it('commutes at boundary: minimum withdrawal', () => {
    const concrete = createAccount(100, StatusCode.Active);
    const absBefore = abstract(concrete);
    concrete.withdraw(1);
    expect(abstract(concrete)).toEqual(
      abstractWithdraw(absBefore, 1),
    );
  });

  it('commutes for all valid inputs (property)', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 1000000 }),
        fc.integer({ min: 1, max: 1000000 }),
        (balance, amount) => {
          const concrete = createAccount(balance, StatusCode.Active);
          const absBefore = abstract(concrete);
          fc.pre(withdrawPrecondition(absBefore, amount));
          concrete.withdraw(amount);
          const absAfter = abstractWithdraw(absBefore, amount);
          expect(abstract(concrete)).toEqual(absAfter);
        },
      ),
    );
  });
});

// --- GetBalance commutativity ---

describe('Refinement: GetBalance', () => {
  it('concrete query matches abstract query', () => {
    const concrete = createAccount(350, StatusCode.Active);
    expect(concrete.getBalance()).toBe(
      abstractGetBalance(abstract(concrete)),
    );
  });

  it('matches for all valid states (property)', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 1000000 }),
        fc.constantFrom(
          StatusCode.Pending,
          StatusCode.Active,
          StatusCode.Suspended,
          StatusCode.Closed,
        ),
        (balance, statusCode) => {
          const concrete = createAccount(balance, statusCode);
          expect(concrete.getBalance()).toBe(
            abstractGetBalance(abstract(concrete)),
          );
        },
      ),
    );
  });
});
```

Report:

```markdown
## Abstraction Function

**Abstract state**: Account (balance, status)
**Concrete state**: BankAccount (balance, statusCode, lastModified)

| Abstract Field | Concrete Field | Mapping |
|----------------|----------------|---------|
| balance : Nat | balance: number | Direct (identity) |
| status : Status | statusCode: StatusCode | Translated via mapStatusCode |
| - | lastModified: Date | Ignored (implementation detail) |

## Commutativity Tests

**Specification**: docs/account.tex
**Implementation**: src/account.ts

| # | Operation | Kind | Example tests | Property tests | Status |
|---|-----------|------|---------------|----------------|--------|
| 1 | Init | init | 1 | - | generated |
| 2 | Deposit | Delta | 3 | 1 | generated |
| 3 | Withdraw | Delta | 3 | 1 | generated |
| 4 | GetBalance | Xi | 1 | 1 | generated |

### Summary

- **Operations covered**: 4
- **Example-based tests**: 8
- **Property-based tests**: 3
- **Total test cases**: 11

### Generated Files

- `src/account.abstraction.ts` (abstraction function + abstract operations)
- `src/account.refinement.test.ts` (commutativity tests)

### Next Steps

1. **Review the abstraction function** in `src/account.abstraction.ts`.
   This is the critical piece -- an incorrect mapping will make tests
   pass even when the implementation is wrong.
2. Run `npm test` to execute the commutativity tests.
3. If any test fails, check (in order): abstraction function,
   implementation code, abstract operation function.
4. For systematic test inputs, run `/z-spec:partition docs/account.tex`
   and incorporate the partition values.
```

## Integration with Other Commands

### With /z-spec:check

Always type-check the specification before running refinement.
`/z-spec:check` validates Z syntax; `/z-spec:refine` verifies
that the implementation correctly refines the spec.

### With /z-spec:model2code

`/z-spec:model2code` generates implementation code from the spec.
`/z-spec:refine` then verifies that the generated (or modified)
code still correctly refines the spec. They form a natural
workflow: generate, customize, then verify.

### With /z-spec:prove

`/z-spec:prove` generates invariant preservation proofs about
the specification itself. `/z-spec:refine --lean` generates
commutativity proofs that the implementation refines the spec.
Together they provide two layers: the spec is internally
consistent (prove), and the code implements the spec (refine).

### With /z-spec:partition

`/z-spec:partition` derives systematic test inputs via TTF tactics.
These partition values are excellent inputs for commutativity
tests. Run partition first, then use those values in refinement
tests for maximum coverage.

### With /z-spec:test (oracle testing)

`/z-spec:test` uses random operation sequences to check the
implementation against the spec via ProB animation. `/z-spec:refine`
proves commutativity per-operation with an explicit abstraction
function. Oracle testing finds bugs through exploration; refinement
provides a structured correctness argument. This command provides
the strongest correctness guarantee available in the plugin.

## Reference

- Z notation syntax: `reference/z-notation.md`
- Schema patterns: `reference/schema-patterns.md`
- Lean 4 type mappings: `reference/lean4-patterns.md`
- Test assertion patterns: `reference/test-patterns.md`
- Woodcock & Davies, "Using Z: Specification, Refinement, and Proof"
  (the theoretical foundation for data refinement via abstraction
  functions and commutativity diagrams)
