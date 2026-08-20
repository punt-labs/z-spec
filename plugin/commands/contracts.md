---
description: Generate runtime contracts (preconditions, postconditions, invariants) from a Z specification
argument-hint: "[spec.tex] [language: swift|typescript|python|kotlin] [--invariants-only] [--wrap] [--strip]"
allowed-tools: Bash(fuzz:*), Bash(which:*), Read, Glob, Grep, Write
---

# /z-spec:contracts - Generate Runtime Contracts

Generate runtime precondition, postcondition, and invariant assertion
functions in the target language from Z schemas. Unlike `/z-spec:model2code`
which generates implementation code, this command generates **checks** --
assertion functions that verify spec conformance at runtime.

Contracts are the executable bridge between specification and
implementation. They encode Z predicates as runtime assertions so
that violations are caught immediately rather than silently corrupting
state.

## Input

Arguments: $ARGUMENTS

Parse arguments:

- First positional argument: Z specification file (default: search `docs/*.tex`)
- Second positional argument or auto-detect: target language (swift, typescript, python, kotlin)
- `--invariants-only`: generate only state invariant checks (no operation contracts)
- `--wrap`: also generate wrapper functions with before/after assertion sandwiches
- `--strip`: emit no-op stubs (empty function bodies) for production builds

## Process

### 0. Prerequisites

The specification should exist and be type-checked. If the spec
has not been checked, suggest running `/z-spec:check` first but
do not block -- contracts can still be generated from a
syntactically valid spec.

Verify fuzz is available for type-checking:

```bash
which fuzz >/dev/null 2>&1 || echo "FUZZ_NOT_FOUND"
```

If fuzz is found, run a type-check to confirm the spec is valid:

```bash
fuzz -t <spec.tex>
```

If fuzz reports errors, warn the user but continue. Contract
generation does not require a passing type-check, but the
generated assertions may reference invalid types.

No other external tools are needed.

### 1. Locate the Specification

If a file path is provided, use it directly.

If no file specified:

- Look in `docs/` for `.tex` files containing Z specifications
- If multiple found, ask user to specify

Read the specification file.

### 2. Detect Target Language

If a language is explicitly provided as the second argument, use it.

Otherwise auto-detect from project files:

| File Present | Language |
|--------------|----------|
| `Package.swift`, `*.xcodeproj` | Swift |
| `package.json`, `tsconfig.json` | TypeScript |
| `pyproject.toml`, `setup.py`, `requirements.txt` | Python |
| `build.gradle.kts`, `pom.xml` | Kotlin |

If detection is ambiguous or fails, ask the user to specify.

### 3. Parse the Specification

Scan the specification and extract the constructs needed for
contract generation. Each subsection describes what to look for.

#### 3a. Free Types

Look for free type definitions in `\begin{zed}` blocks:

```latex
\begin{zed}
Status ::= pending | active | suspended | closed
\end{zed}
```

Record the type name and all constructors. These are needed
for enum validation assertions.

#### 3b. Axiomatic Definitions

Look for `\begin{axdef}` blocks with global constants:

```latex
\begin{axdef}
MAX\_LEVEL : \nat
\where
MAX\_LEVEL = 26
\end{axdef}
```

Record each constant name and its defining value. Constants
appear in invariant and precondition bounds.

#### 3c. State Schemas

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

- **Name**: The schema name
- **Fields**: Each variable name and its Z type
- **Invariants**: All predicates in the `\where` block

#### 3d. Operation Schemas

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
- **Kind**: `\Delta` (state-changing) or `\Xi` (query)
- **State schema**: The referenced state schema name
- **Inputs**: Variables ending in `?` with their types
- **Outputs**: Variables ending in `!` with their types
- **Preconditions**: Predicates referencing only unprimed state
  variables and/or inputs
- **Effects**: Predicates referencing primed variables (`x'`)
- **Frame conditions**: Predicates of the form `x' = x`

### 4. Classify Predicates

For each operation, classify every predicate clause in the
`\where` block. This classification determines which contract
function each predicate belongs to.

| Classification | Rule | Contract Function |
|----------------|------|-------------------|
| **Precondition** | References only unprimed state vars and/or inputs | `assert<Op>Pre` |
| **Effect** | References primed variables (`x'`) and is not a frame | `assert<Op>Post` |
| **Frame** | Has form `x' = x` (no change) | `assert<Op>Post` |
| **Invariant** | In state schema `\where` block | `assert<State>Invariant` |
| **Output definition** | Defines output (`x!`) in terms of state/inputs | `assert<Op>Post` |

Handle disjunctive predicates by decomposing into branches.
If an operation has `P \lor Q` in its predicate block, the
postcondition assertion should check `(P) || (Q)` -- both
branches are valid outcomes.

Handle implications: `P \implies Q` becomes
`!P || Q` in the assertion.

### 5. Generate Contract Functions

Generate one output file containing all assertion functions.
Group functions by schema: state invariants first, then
operation contracts in specification order.

#### 5a. State Invariant Assertions

For each state schema with a `\where` block, generate an
assertion function that checks every invariant predicate:

**TypeScript:**

```typescript
// Generated from Z schema Account
export function assertAccountInvariant(state: Account): void {
  assert(state.balance >= 0 || state.status === Status.Suspended,
    'Invariant: balance >= 0 \\/ status = suspended');
  assert(state.status !== Status.Closed || state.balance === 0,
    'Invariant: status = closed => balance = 0');
}
```

**Swift:**

```swift
// Generated from Z schema Account
func assertAccountInvariant(_ state: Account) {
  precondition(state.balance >= 0 || state.status == .suspended,
    "Invariant: balance >= 0 \\/ status = suspended")
  precondition(state.status != .closed || state.balance == 0,
    "Invariant: status = closed => balance = 0")
}
```

**Python:**

```python
# Generated from Z schema Account
def assert_account_invariant(state: Account) -> None:
    assert state.balance >= 0 or state.status == Status.SUSPENDED, \
        'Invariant: balance >= 0 \\/ status = suspended'
    assert state.status != Status.CLOSED or state.balance == 0, \
        'Invariant: status = closed => balance = 0'
```

**Kotlin:**

```kotlin
// Generated from Z schema Account
fun assertAccountInvariant(state: Account) {
    check(state.balance >= 0 || state.status == Status.SUSPENDED) {
        "Invariant: balance >= 0 \\/ status = suspended"
    }
    check(state.status != Status.CLOSED || state.balance == 0) {
        "Invariant: status = closed => balance = 0"
    }
}
```

If `--invariants-only` is specified, stop here. Do not generate
operation contract functions.

#### 5b. Precondition Assertions

For each operation, generate an assertion function that checks
all preconditions. Inputs are function parameters alongside
the state.

**TypeScript:**

```typescript
// Generated from Z schema Deposit
export function assertDepositPre(state: Account, amount: number): void {
  assert(amount > 0, 'Pre: amount > 0 (nat_1)');
  assert(state.status === Status.Active, 'Pre: status = active');
}
```

**Swift:**

```swift
// Generated from Z schema Deposit
func assertDepositPre(_ state: Account, amount: Int) {
  precondition(amount > 0, "Pre: amount > 0 (nat_1)")
  precondition(state.status == .active, "Pre: status = active")
}
```

**Python:**

```python
# Generated from Z schema Deposit
def assert_deposit_pre(state: Account, amount: int) -> None:
    assert amount > 0, 'Pre: amount > 0 (nat_1)'
    assert state.status == Status.ACTIVE, 'Pre: status = active'
```

**Kotlin:**

```kotlin
// Generated from Z schema Deposit
fun assertDepositPre(state: Account, amount: Int) {
    require(amount > 0) { "Pre: amount > 0 (nat_1)" }
    require(state.status == Status.ACTIVE) { "Pre: status = active" }
}
```

**Type constraint assertions**: Z types carry implicit constraints.
Generate assertions for these as well:

| Z Type | Implicit Assertion |
|--------|--------------------|
| `\nat` | `x >= 0` |
| `\nat_1` | `x > 0` |
| `x \in A \upto B` | `x >= A && x <= B` |
| `x \in S` (finite set) | Membership check |

#### 5c. Postcondition Assertions

For each Delta operation, generate an assertion function that
checks all effects and frame conditions. The function takes
the before-state, after-state, and inputs.

**TypeScript:**

```typescript
// Generated from Z schema Deposit
export function assertDepositPost(
  before: Account,
  after: Account,
  amount: number
): void {
  // Effects
  assert(after.balance === before.balance + amount,
    "Post: balance' = balance + amount");
  // Frame conditions
  assert(after.status === before.status,
    "Frame: status' = status (unchanged)");
}
```

**Swift:**

```swift
// Generated from Z schema Deposit
func assertDepositPost(before: Account, after: Account, amount: Int) {
  assert(after.balance == before.balance + amount,
    "Post: balance' = balance + amount")
  assert(after.status == before.status,
    "Frame: status' = status (unchanged)")
}
```

**Python:**

```python
# Generated from Z schema Deposit
def assert_deposit_post(
    before: Account, after: Account, amount: int
) -> None:
    # Effects
    assert after.balance == before.balance + amount, \
        "Post: balance' = balance + amount"
    # Frame conditions
    assert after.status == before.status, \
        "Frame: status' = status (unchanged)"
```

**Kotlin:**

```kotlin
// Generated from Z schema Deposit
fun assertDepositPost(before: Account, after: Account, amount: Int) {
    // Effects
    check(after.balance == before.balance + amount) {
        "Post: balance' = balance + amount"
    }
    // Frame conditions
    check(after.status == before.status) {
        "Frame: status' = status (unchanged)"
    }
}
```

**Xi operations**: For query operations (`\Xi`), the postcondition
asserts that the entire state is unchanged. Generate a single
frame assertion covering all state fields:

```typescript
export function assertGetBalancePost(before: Account, after: Account): void {
  assert(after.balance === before.balance, 'Frame: balance unchanged');
  assert(after.status === before.status, 'Frame: status unchanged');
}
```

#### 5d. Disjunctive Operations

When an operation has multiple behavioral branches (disjunction),
the postcondition assertion checks that at least one branch
holds:

```latex
\begin{schema}{TryWithdraw}
\Delta Account \\
amount? : \nat_1 \\
success! : ZBOOL
\where
(amount? \leq balance \land balance' = balance - amount? \land success! = ztrue)
\lor
(amount? > balance \land balance' = balance \land success! = zfalse)
\end{schema}
```

**TypeScript:**

```typescript
export function assertTryWithdrawPost(
  before: Account,
  after: Account,
  amount: number,
  success: boolean
): void {
  const branch1 =
    amount <= before.balance &&
    after.balance === before.balance - amount &&
    success === true;
  const branch2 =
    amount > before.balance &&
    after.balance === before.balance &&
    success === false;
  assert(branch1 || branch2,
    'Post: must satisfy success or failure branch');
}
```

#### 5e. Collection and Map Assertions

For specifications involving sets, sequences, and partial functions,
generate appropriate collection assertions:

| Z Predicate | TypeScript Assertion | Swift Assertion |
|-------------|---------------------|-----------------|
| `x \in S` | `assert(s.has(x), ...)` | `precondition(s.contains(x), ...)` |
| `x \notin S` | `assert(!s.has(x), ...)` | `precondition(!s.contains(x), ...)` |
| `S \subseteq T` | `assert([...s].every(e => t.has(e)), ...)` | `precondition(s.isSubset(of: t), ...)` |
| `\# S = n` | `assert(s.size === n, ...)` | `precondition(s.count == n, ...)` |
| `x \mapsto y \in f` | `assert(f.get(x) === y, ...)` | `precondition(f[x] == y, ...)` |
| `\dom f = S` | Domain equality check | Domain equality check |

### 6. Generate Wrapper Functions (--wrap flag)

If `--wrap` is specified, generate wrapper functions for each
Delta operation. A wrapper sandwiches the actual operation call
between assertion checks:

1. Assert state invariant (pre)
2. Assert operation precondition
3. Snapshot the before-state
4. Call the actual operation
5. Assert operation postcondition (before, after, inputs)
6. Assert state invariant (post)

This enforces the full Hoare triple: `{Inv /\ Pre} op {Inv /\ Post}`.

**TypeScript:**

```typescript
export function depositWithContracts(
  state: Account,
  amount: number
): void {
  assertAccountInvariant(state);
  assertDepositPre(state, amount);
  const before = structuredClone(state);
  deposit(state, amount);
  assertDepositPost(before, state, amount);
  assertAccountInvariant(state);
}
```

**Swift:**

```swift
func depositWithContracts(_ state: inout Account, amount: Int) {
    assertAccountInvariant(state)
    assertDepositPre(state, amount: amount)
    let before = state
    state.deposit(amount: amount)
    assertDepositPost(before: before, after: state, amount: amount)
    assertAccountInvariant(state)
}
```

**Python:**

```python
def deposit_with_contracts(state: Account, amount: int) -> None:
    assert_account_invariant(state)
    assert_deposit_pre(state, amount)
    before = copy.deepcopy(state)
    state.deposit(amount)
    assert_deposit_post(before, state, amount)
    assert_account_invariant(state)
```

**Kotlin:**

```kotlin
fun depositWithContracts(state: Account, amount: Int) {
    assertAccountInvariant(state)
    assertDepositPre(state, amount)
    val before = state.copy()
    state.deposit(amount)
    assertDepositPost(before, state, amount)
    assertAccountInvariant(state)
}
```

**Xi operations**: Query wrappers assert state invariant and
that the state is unchanged after the call:

```typescript
export function getBalanceWithContracts(state: Account): number {
  assertAccountInvariant(state);
  const before = structuredClone(state);
  const result = getBalance(state);
  assertGetBalancePost(before, state);
  assertAccountInvariant(state);
  return result;
}
```

### 6b. Strip Mode (--strip flag)

If `--strip` is specified, generate the same function signatures
but with empty bodies. This produces no-op stubs that compile
identically to the real contracts, allowing production builds to
link against the same interface without runtime overhead.

For each assertion function, emit an empty body:

- **TypeScript**: `export function assertAccountInvariant(state: Account): void { }`
- **Swift**: `func assertAccountInvariant(_ state: Account) { }`
- **Python**: `def assert_account_invariant(state: Account) -> None: pass`
- **Kotlin**: `fun assertAccountInvariant(state: Account): Unit { }`

If `--wrap` and `--strip` are both specified, wrappers delegate
to the underlying operation directly without assertion calls.

### 7. Write Output File

Write the generated contracts to a file following language
conventions:

| Language | Filename | Location |
|----------|----------|----------|
| Swift | `<Name>Contracts.swift` | Same directory as model code |
| TypeScript | `<name>.contracts.ts` | Same directory as model code |
| Python | `<name>_contracts.py` | Same directory as model code |
| Kotlin | `<Name>Contracts.kt` | Same directory as model code |

Where `<Name>` is the primary state schema name from the spec.

**File header**: Include a generation comment at the top:

**TypeScript:**

```typescript
/**
 * Runtime contracts generated from Z specification: <spec-file>
 *
 * These assertion functions verify that the implementation
 * conforms to the formal specification at runtime. Each function
 * encodes predicates from the Z schema it references.
 *
 * Usage:
 *   import { assertAccountInvariant, assertDepositPre } from './account.contracts';
 *   assertAccountInvariant(state);
 *   assertDepositPre(state, amount);
 *
 * Generated by /z-spec:contracts
 */
```

**Swift:**

```swift
/// Runtime contracts generated from Z specification: <spec-file>
///
/// These assertion functions verify that the implementation
/// conforms to the formal specification at runtime. Each function
/// encodes predicates from the Z schema it references.
///
/// Generated by /z-spec:contracts
```

**Imports**: Include necessary imports at the top of the file:

- TypeScript: `import assert from 'node:assert';` (or project assert utility)
- Swift: No import needed (`precondition` is built-in)
- Python: `import copy` (if `--wrap` is used)
- Kotlin: No import needed (`require`/`check` are built-in)

Also import the model types generated by `/z-spec:model2code`
or the project's own type definitions.

**Do not overwrite** existing contract files without asking. If
a contracts file already exists, warn and ask the user before
replacing it.

### 8. Report Summary

After generating contracts, report a summary table:

```markdown
## Contract Summary

**Specification**: docs/account.tex
**Language**: TypeScript
**Output**: src/account.contracts.ts

### State Invariants

| Schema | Predicates | Assertions |
|--------|-----------|------------|
| Account | 2 | 2 |

### Operation Contracts

| Operation | Kind | Pre | Post | Frame | Total |
|-----------|------|-----|------|-------|-------|
| Deposit | Delta | 2 | 1 | 1 | 4 |
| Withdraw | Delta | 3 | 1 | 1 | 5 |
| TryWithdraw | Delta | 1 | 2 (branches) | 0 | 3 |
| GetBalance | Xi | 0 | 0 | 2 | 2 |
| CloseAccount | Delta | 2 | 2 | 0 | 4 |
| **Total** | | **8** | **6** | **4** | **18** |

**18 runtime assertions generated.**
```

If `--wrap` was used, also report:

```markdown
### Wrapper Functions

5 wrapper functions generated (sandwich pattern: Inv + Pre + Op + Post + Inv).
```

If `--invariants-only` was used:

```markdown
### Invariants Only

2 invariant assertions generated. Operation contracts skipped (--invariants-only).
```

## Predicate Translation Reference

This table maps Z predicates to assertion expressions in each
target language. Use this when translating `\where` block
clauses into runtime checks.

| Z Predicate | TypeScript | Swift | Python | Kotlin |
|-------------|-----------|-------|--------|--------|
| `x \geq N` | `x >= N` | `x >= N` | `x >= N` | `x >= N` |
| `x \leq N` | `x <= N` | `x <= N` | `x <= N` | `x <= N` |
| `x > N` | `x > N` | `x > N` | `x > N` | `x > N` |
| `x < N` | `x < N` | `x < N` | `x < N` | `x < N` |
| `x = y` | `x === y` | `x == y` | `x == y` | `x == y` |
| `x \neq y` | `x !== y` | `x != y` | `x != y` | `x != y` |
| `P \land Q` | `P && Q` | `P && Q` | `P and Q` | `P && Q` |
| `P \lor Q` | `P \|\| Q` | `P \|\| Q` | `P or Q` | `P \|\| Q` |
| `P \implies Q` | `!P \|\| Q` | `!P \|\| Q` | `not P or Q` | `!P \|\| Q` |
| `\lnot P` | `!P` | `!P` | `not P` | `!P` |
| `x \in S` | `s.has(x)` | `s.contains(x)` | `x in s` | `x in s` |
| `x \notin S` | `!s.has(x)` | `!s.contains(x)` | `x not in s` | `x !in s` |
| `\# S` | `s.size` | `s.count` | `len(s)` | `s.size` |
| `S \subseteq T` | `[...s].every(e => t.has(e))` | `s.isSubset(of: t)` | `s <= t` | `s.all { it in t }` |
| `x \in A \upto B` | `x >= A && x <= B` | `(A...B).contains(x)` | `A <= x <= B` | `x in A..B` |

## Assertion Function Reference

Summary of which assertion construct to use in each language:

| Purpose | TypeScript | Swift | Python | Kotlin |
|---------|-----------|-------|--------|--------|
| Invariant | `assert(expr, msg)` | `precondition(expr, msg)` | `assert expr, msg` | `check(expr) { msg }` |
| Precondition | `assert(expr, msg)` | `precondition(expr, msg)` | `assert expr, msg` | `require(expr) { msg }` |
| Postcondition | `assert(expr, msg)` | `assert(expr, msg)` | `assert expr, msg` | `check(expr) { msg }` |
| Frame | `assert(expr, msg)` | `assert(expr, msg)` | `assert expr, msg` | `check(expr) { msg }` |

Kotlin distinguishes `require` (preconditions -- throws
`IllegalArgumentException`) from `check` (postconditions and
invariants -- throws `IllegalStateException`). Other languages
use a single assertion mechanism.

## Type Mappings

Use the same type mappings as `/z-spec:model2code`:

| Z Type | Swift | TypeScript | Python | Kotlin |
|--------|-------|------------|--------|--------|
| `\nat` | `Int` (with `>= 0` check) | `number` | `int` | `Int` |
| `\nat_1` | `Int` (with `> 0` check) | `number` | `int` | `Int` |
| `\num` | `Int` | `number` | `int` | `Int` |
| `X \pfun Y` | `[X: Y]` | `Map<X, Y>` | `dict[X, Y]` | `Map<X, Y>` |
| `\power X` | `Set<X>` | `Set<X>` | `set[X]` | `Set<X>` |
| `\seq X` | `[X]` | `X[]` | `list[X]` | `List<X>` |
| Free type | `enum` | `enum` (string) | `Enum` | `enum class` |

## Error Handling

| Error | Response |
|-------|----------|
| Specification not found | "No Z specification found. Specify path or create one with `/z-spec:code2model`." |
| No state schemas | "No state schemas with invariants found. Nothing to generate contracts for." |
| No operation schemas (without `--invariants-only`) | "No operation schemas found (schemas with `\Delta` or `\Xi`). Generating invariant contracts only." |
| Unsupported language | "Language not supported. Supported: Swift, TypeScript, Python, Kotlin." |
| Parse error in schema | "Could not parse schema {name}. Skipping." (continue with others) |
| fuzz not found | "fuzz not installed. Skipping type-check. Contracts will be generated but may reference invalid types. Run `/z-spec:setup` to install fuzz." |
| fuzz reports errors | "Specification has type errors (see above). Contracts generated but may be incorrect. Fix spec errors and regenerate." |
| Existing contracts file | "Contracts file already exists at {path}. Overwrite? (Proceeding will replace the file.)" |
| No invariants in state schema | "State schema {name} has no `\\where` block. Skipping invariant generation for this schema." |

## Worked Example

Given this Z specification (`docs/counter.tex`):

```latex
\begin{axdef}
MAX\_COUNT : \nat
\where
MAX\_COUNT = 100
\end{axdef}

\begin{schema}{Counter}
value : \nat \\
limit : \nat
\where
value \leq limit \\
limit \leq MAX\_COUNT
\end{schema}

\begin{schema}{InitCounter}
Counter'
\where
value' = 0 \\
limit' = MAX\_COUNT
\end{schema}

\begin{schema}{Increment}
\Delta Counter
\where
value < limit \\
value' = value + 1 \\
limit' = limit
\end{schema}

\begin{schema}{Reset}
\Delta Counter
\where
value' = 0 \\
limit' = limit
\end{schema}

\begin{schema}{GetValue}
\Xi Counter \\
result! : \nat
\where
result! = value
\end{schema}
```

Running `/z-spec:contracts docs/counter.tex typescript --wrap`
generates `counter.contracts.ts`:

```typescript
/**
 * Runtime contracts generated from Z specification: docs/counter.tex
 *
 * These assertion functions verify that the implementation
 * conforms to the formal specification at runtime.
 *
 * Generated by /z-spec:contracts
 */

import assert from 'node:assert';
import type { Counter } from './counter';
import { increment, reset, getValue } from './counter';

// --- Constants ---

const MAX_COUNT = 100;

// --- State Invariants ---

/** Assert Counter state invariant: value <= limit /\ limit <= MAX_COUNT */
export function assertCounterInvariant(state: Counter): void {
  assert(state.value >= 0, 'Invariant: value >= 0 (nat)');
  assert(state.limit >= 0, 'Invariant: limit >= 0 (nat)');
  assert(state.value <= state.limit, 'Invariant: value <= limit');
  assert(state.limit <= MAX_COUNT, 'Invariant: limit <= MAX_COUNT');
}

// --- Increment ---

/** Assert Increment preconditions */
export function assertIncrementPre(state: Counter): void {
  assert(state.value < state.limit, 'Pre: value < limit');
}

/** Assert Increment postconditions and frame */
export function assertIncrementPost(
  before: Counter,
  after: Counter
): void {
  assert(after.value === before.value + 1,
    "Post: value' = value + 1");
  assert(after.limit === before.limit,
    "Frame: limit' = limit (unchanged)");
}

/** Increment with full contract checking */
export function incrementWithContracts(state: Counter): void {
  assertCounterInvariant(state);
  assertIncrementPre(state);
  const before = structuredClone(state);
  increment(state);
  assertIncrementPost(before, state);
  assertCounterInvariant(state);
}

// --- Reset ---

/** Assert Reset preconditions (none -- always allowed) */
export function assertResetPre(_state: Counter): void {
  // No preconditions
}

/** Assert Reset postconditions and frame */
export function assertResetPost(
  before: Counter,
  after: Counter
): void {
  assert(after.value === 0, "Post: value' = 0");
  assert(after.limit === before.limit,
    "Frame: limit' = limit (unchanged)");
}

/** Reset with full contract checking */
export function resetWithContracts(state: Counter): void {
  assertCounterInvariant(state);
  assertResetPre(state);
  const before = structuredClone(state);
  reset(state);
  assertResetPost(before, state);
  assertCounterInvariant(state);
}

// --- GetValue ---

/** Assert GetValue postcondition (Xi -- state unchanged) */
export function assertGetValuePost(
  before: Counter,
  after: Counter
): void {
  assert(after.value === before.value, 'Frame: value unchanged');
  assert(after.limit === before.limit, 'Frame: limit unchanged');
}

/** GetValue with full contract checking */
export function getValueWithContracts(state: Counter): number {
  assertCounterInvariant(state);
  const before = structuredClone(state);
  const result = getValue(state);
  assertGetValuePost(before, state);
  assertCounterInvariant(state);
  return result;
}
```

Report:

```markdown
## Contract Summary

**Specification**: docs/counter.tex
**Language**: TypeScript
**Output**: counter.contracts.ts

### State Invariants

| Schema | Predicates | Assertions |
|--------|-----------|------------|
| Counter | 2 (+2 type) | 4 |

### Operation Contracts

| Operation | Kind | Pre | Post | Frame | Total |
|-----------|------|-----|------|-------|-------|
| Increment | Delta | 1 | 1 | 1 | 3 |
| Reset | Delta | 0 | 1 | 1 | 2 |
| GetValue | Xi | 0 | 0 | 2 | 2 |
| **Total** | | **1** | **2** | **4** | **7** |

**11 runtime assertions generated (4 invariant + 7 operation).**

### Wrapper Functions

3 wrapper functions generated (sandwich pattern: Inv + Pre + Op + Post + Inv).
```

## Integration with Other Commands

### With /z-spec:model2code

Contracts import and reference the same types and function names
generated by `/z-spec:model2code`. Run `model2code` first to
produce the implementation, then `contracts` to produce the
assertion layer. The contracts file imports from the model file.

### With /z-spec:partition

Partition tests are structural -- they enumerate distinct
behavioral classes and test each with concrete values.
Contracts are operational -- they check every state transition
at runtime. The two are complementary: partitions catch
specification coverage gaps at test time, contracts catch
conformance violations at runtime.

### With /z-spec:audit

After generating contracts, run `/z-spec:audit` to verify that
the contracts cover all specification predicates. The audit
command can cross-reference assertion messages against Z
predicates.

### With /z-spec:prove

Proved obligations in Lean provide deductive certainty that
invariants are preserved. Contracts provide runtime enforcement
of the same properties. For critical systems, use both:
proofs for verified properties, contracts for defense in depth
against implementation bugs.

## Reference

- Z notation syntax: `reference/z-notation.md`
- Schema patterns: `reference/schema-patterns.md`
- Test assertion patterns: `reference/test-patterns.md`
- Type mappings: `commands/model2code.md`
