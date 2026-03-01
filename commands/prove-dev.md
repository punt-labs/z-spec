---
description: Generate Lean 4 proof obligations from a Z specification
argument-hint: "[spec.tex] [--obligations=all|init|preserve] [--no-mathlib]"
allowed-tools: Bash(which:*), Bash(elan:*), Bash(lean:*), Bash(lake:*), Read, Glob, Grep, Write
---

# /z-spec:prove - Generate Lean 4 Proof Obligations

Translate a Z specification into Lean 4 proof obligations that
formalize the key correctness properties: initialization establishes
the state invariant, and every operation preserves it.

## Input

Arguments: $ARGUMENTS

Parse arguments:

- First positional argument: Z specification file (default: search `docs/*.tex`)
- `--obligations=all|init|preserve` - which proof obligations to generate (default: `all`)
- `--no-mathlib` - generate standalone Lean without Mathlib dependency (simpler but fewer tactics)

## Process

### 0. Prerequisites

Verify Lean 4 and Lake are installed:

```bash
which lean >/dev/null 2>&1 || echo "LEAN_NOT_FOUND"
which lake >/dev/null 2>&1 || echo "LAKE_NOT_FOUND"
```

**If lean or lake not found**: Stop and tell the user:
> Lean 4 is not installed. Run `/z-spec:setup lean` to install
> the Lean 4 toolchain via elan.

Verify version compatibility:

```bash
lean --version 2>&1
```

The output should show Lean 4.x. If it shows Lean 3.x or an error,
advise the user to update via `elan update`.

The Z specification should already exist and have been type-checked
(via `/z-spec:check`). If the user has not done this, suggest it
but do not block — the translation can still proceed from a
syntactically valid spec.

### 1. Locate the Specification

If a file path is provided, use it directly.

If no file specified:

- Look in `docs/` for `.tex` files containing Z specifications
- If multiple found, ask user to specify

Read the specification file.

### 2. Parse the Specification

Scan the specification and extract the following constructs.
Each subsection describes what to look for and what to record.

#### 2a. Given Sets

Look for given set declarations in `\begin{zed}` blocks:

```latex
\begin{zed}
[USERID, SESSIONID]
\end{zed}
```

Record each name. These become opaque types in Lean.

#### 2b. Free Types

Look for free type definitions in `\begin{zed}` blocks:

```latex
\begin{zed}
Status ::= pending | active | suspended | closed
\end{zed}
```

Record the type name and all constructors. These become
`inductive` types in Lean.

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
These become `def` declarations in Lean.

#### 2d. State Schemas

Look for state schemas — schemas that are **not** operations
(no `\Delta`, `\Xi`, or primed-only variables) and contain
a `\where` block with invariant predicates:

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

#### 2e. Init Schemas

Look for schemas that initialize the state. An init schema
typically includes `State'` (the primed state) and defines
only primed variables:

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

### 3. Check or Create Lean Project

#### 3a. Reuse Existing Project

If a `proofs/` directory exists with `lakefile.toml`, reuse it:

```bash
ls proofs/lakefile.toml 2>/dev/null && echo "PROJECT_EXISTS"
```

If the project exists, check that `lean-toolchain` matches the
expected version. If it differs, warn but do not overwrite.

#### 3b. Create New Project

If no project exists, create the directory structure:

```
proofs/
  lean-toolchain
  lakefile.toml
  ZSpec/
    Basic.lean
    State.lean
    Operations.lean
    Proofs/
      InitEstablishes.lean
      Preserves.lean
```

**lean-toolchain**:

```
leanprover/lean4:v4.16.0
```

**lakefile.toml** (with Mathlib):

```toml
[package]
name = "ZSpec"
version = "0.1.0"
leanOptions = []

[[require]]
name = "mathlib"
scope = "leanprover-community"
version = "git#master"
```

**lakefile.toml** (with `--no-mathlib`):

```toml
[package]
name = "ZSpec"
version = "0.1.0"
leanOptions = []
```

After creating the project, run `lake update` to fetch dependencies:

```bash
cd proofs && lake update
```

This may take several minutes for Mathlib. Inform the user:
> Fetching Lean dependencies (Mathlib is large, this may take a few
> minutes on first run)...

### 4. Generate Lean Files

Translate each Z construct into idiomatic Lean 4. Use the type
mappings and code patterns described below.

#### 4a. Type Mappings

| Z Type | Lean 4 Type | Notes |
|--------|-------------|-------|
| `[X]` (given set) | `opaque X : Type` | Abstract type, no constructors |
| `\nat` | `Nat` | Built-in natural numbers |
| `\nat_1` | `Nat` | Add `h : n > 0` where needed |
| `\num` | `Int` | Built-in integers |
| `T ::= c1 \| c2 \| ...` | `inductive T` | One constructor per branch |
| `\power X` | `Finset X` | Requires `Mathlib.Data.Finset.Basic` |
| `\seq X` | `List X` | Built-in lists |
| `X \pfun Y` | `X -> Option Y` | Partial function as option-returning |
| `X \fun Y` | `X -> Y` | Total function |
| `X \cross Y` | `X x Y` | Product type |
| `X \rel Y` | `Finset (X x Y)` | Relation as set of pairs |
| `a \upto b` | `Finset.range` or `Finset.Icc a b` | Integer range |
| `\# S` | `S.card` | Finset cardinality |
| `S \cup T` | `S \cup T` | Finset union |
| `S \cap T` | `S \cap T` | Finset intersection |
| `S \setminus T` | `S \ T` | Finset difference |
| `x \in S` | `x \in S` | Membership |
| `\dom f` | Domain of function | Model as needed |
| `\ran f` | Range of function | Model as needed |

#### 4b. Basic.lean

This file contains imports, given set declarations, free types,
and axiomatic definitions.

```lean
/-
  ZSpec.Basic
  Generated from: <spec-file-name>
  Date: <current-date>

  Basic type declarations and definitions.
-/

import Mathlib.Data.Finset.Basic
import Mathlib.Tactic

-- Given sets
opaque UserId : Type
opaque SessionId : Type

-- Instances needed for Finset membership
instance : DecidableEq UserId := sorry
instance : DecidableEq SessionId := sorry

-- Free types
inductive Status where
  | pending
  | active
  | suspended
  | closed
  deriving DecidableEq, Repr

-- Constants
def MAX_BALANCE : Nat := 1000000
```

**Without Mathlib** (`--no-mathlib`):

- Omit `import Mathlib.*` lines
- Replace `Finset` with `List` (with deduplication convention)
- Omit `deriving` clauses that require Mathlib instances

**Rules for given sets**:

- Declare `opaque X : Type` for each given set `[X]`
- Add `instance : DecidableEq X := sorry` so that equality
  is decidable (needed for `Finset` operations)
- If the spec uses `X` in finite sets, also add
  `instance : Fintype X := sorry`

**Rules for free types**:

- Each constructor becomes a Lean constructor (lowercase)
- Derive `DecidableEq` and `Repr` for pattern matching and printing
- If a constructor carries data (`c \ldata T \rdata`), add
  the parameter: `| c : T -> MyType`

#### 4c. State.lean

This file defines the state schema as a structure and the
invariant as a proposition.

```lean
/-
  ZSpec.State
  Generated from: <spec-file-name>

  State schema and invariant.
-/

import ZSpec.Basic

structure Account where
  balance : Int
  status : Status
  deriving Repr

/-- The state invariant: all properties that must hold in every
    reachable state. -/
def Account.invariant (s : Account) : Prop :=
  (s.balance >= 0 \/ s.status = Status.suspended) /\
  (s.status = Status.closed -> s.balance = 0)
```

**Translation rules for invariants**:

| Z Predicate | Lean 4 |
|-------------|--------|
| `P \land Q` | `P /\ Q` |
| `P \lor Q` | `P \/ Q` |
| `P \implies Q` | `P -> Q` |
| `\lnot P` | `Not P` or `!P` (for `Bool`) |
| `x \geq y` | `x >= y` |
| `x \leq y` | `x <= y` |
| `x \neq y` | `x != y` |
| `x = y` | `x = y` |
| `x \in S` | `x \in S` |
| `x \notin S` | `x \notin S` |
| `\forall x : T @ P` | `\forall (x : T), P` |
| `\exists x : T @ P` | `\exists (x : T), P` |

**Multiple state schemas**: If the specification has multiple
state schemas, generate a structure for each. If operations
reference a composed state, generate a combined structure.

#### 4d. Operations.lean

This file defines the initial state, precondition predicates,
and operation functions.

```lean
/-
  ZSpec.Operations
  Generated from: <spec-file-name>

  Initial state, operation preconditions, and transition functions.
-/

import ZSpec.State

-- Init
/-- The initial state as defined by InitAccount. -/
def initAccount : Account :=
  { balance := 0, status := Status.pending }

-- Operation preconditions

/-- Precondition for Deposit: status must be active. -/
def deposit_precondition (s : Account) (amount : Nat) : Prop :=
  s.status = Status.active /\ amount > 0

/-- Deposit operation: adds amount to balance. -/
def deposit (s : Account) (amount : Nat) : Account :=
  { s with balance := s.balance + amount }

-- Xi operations (queries)

/-- GetBalance precondition (always true for queries). -/
def getBalance_precondition (s : Account) : Prop := True

/-- GetBalance result. -/
def getBalance (s : Account) : Int := s.balance
```

**Translation rules for operations**:

- **Delta operations** return a new state (`Account`).
  Use `{ s with field := newValue }` for field updates.
- **Xi operations** return the output type, not a new state.
  The state is unchanged (the frame condition is implicit).
- **Inputs** (`x?`) become function parameters (drop the `?`).
- **Outputs** (`x!`) become the return value (drop the `!`).
  If multiple outputs, return a product type.
- **Preconditions** become separate `_precondition` predicates
  returning `Prop`.
- **Frame conditions** (`x' = x`) are implicit in the `{ s with ... }`
  pattern — only changed fields are listed.

**Handling disjunctive operations**: If an operation has multiple
behavioral branches (disjunction in the predicate), model it as
a function that pattern-matches on the branch condition:

```lean
def tryWithdraw (s : Account) (amount : Nat) : Account x Bool :=
  if amount <= s.balance then
    ({ s with balance := s.balance - amount }, true)
  else
    (s, false)
```

#### 4e. Proofs/InitEstablishes.lean

This file contains the proof obligation that the initial state
satisfies the state invariant.

```lean
/-
  ZSpec.Proofs.InitEstablishes
  Generated from: <spec-file-name>

  Proof obligation: the initial state satisfies the invariant.
-/

import ZSpec.Operations

/-- The initial state satisfies the Account invariant. -/
theorem init_establishes_invariant :
    initAccount.invariant := by
  sorry
```

**One theorem per init schema**. If the spec has multiple
init schemas for different state schemas, generate a theorem
for each.

#### 4f. Proofs/Preserves.lean

This file contains proof obligations that each Delta operation
preserves the state invariant when its precondition holds.

```lean
/-
  ZSpec.Proofs.Preserves
  Generated from: <spec-file-name>

  Proof obligations: each operation preserves the invariant
  when applied to a valid state with a satisfied precondition.
-/

import ZSpec.Operations

/-- Deposit preserves the Account invariant. -/
theorem deposit_preserves_invariant
    (s : Account) (amount : Nat)
    (h_inv : s.invariant)
    (h_pre : deposit_precondition s amount) :
    (deposit s amount).invariant := by
  sorry

/-- Withdraw preserves the Account invariant. -/
theorem withdraw_preserves_invariant
    (s : Account) (amount : Nat)
    (h_inv : s.invariant)
    (h_pre : withdraw_precondition s amount) :
    (withdraw s amount).invariant := by
  sorry
```

**One theorem per Delta operation**. Xi operations do not
change state, so they trivially preserve the invariant and
do not need explicit proof obligations.

**Theorem naming convention**: `<operation>_preserves_invariant`

**Hypotheses**:

- `h_inv : s.invariant` — the pre-state satisfies the invariant
- `h_pre : <op>_precondition s <inputs>` — the precondition holds
- Additional hypotheses for input constraints (e.g., `h_amt : amount > 0`)

**Conclusion**: `(<op> s <inputs>).invariant` — the post-state
satisfies the invariant.

### 5. Filter by --obligations Flag

If `--obligations` is specified, generate only the requested files:

| Flag Value | Files Generated |
|------------|-----------------|
| `all` (default) | Basic, State, Operations, InitEstablishes, Preserves |
| `init` | Basic, State, Operations, InitEstablishes |
| `preserve` | Basic, State, Operations, Preserves |

Always generate Basic.lean, State.lean, and Operations.lean since
the proof files depend on them.

### 6. Attempt Proof Discharge

After generating all files, attempt to discharge simple proof
obligations automatically. This step is best-effort — many
obligations will remain as `sorry`.

#### 6a. Tactic Catalog

Try the following tactics in order for each `sorry`:

| Tactic | When It Works |
|--------|---------------|
| `decide` | Finite, decidable propositions (enumerated types, small bounds) |
| `omega` | Linear arithmetic over `Nat` and `Int` |
| `simp [invariant, precondition_name]` | Unfolding definitions then simplifying |
| `simp only [Function.comp]` | Composition-heavy goals |
| `constructor <;> omega` | Conjunction of arithmetic goals |
| `intro h; cases h <;> omega` | Disjunction in hypothesis |
| `unfold invariant; constructor <;> simp_all` | General invariant unfolding |
| `aesop` | Automated reasoning (Mathlib, slower) |

Without Mathlib (`--no-mathlib`), only `decide`, `omega`, `simp`,
and `constructor` are available.

#### 6b. Discharge Process

For each theorem with `sorry`:

1. Replace `sorry` with the first tactic from the catalog
2. Run `lake build` and capture output
3. If the build succeeds (exit code 0, no errors in the target file),
   keep the tactic
4. If the build fails, try the next tactic
5. If all tactics fail, revert to `sorry`

```bash
cd proofs && lake build 2>&1
```

**Important**: Run `lake build` once after each tactic substitution,
not once per theorem. Batch substitutions where possible to minimize
build cycles:

1. First pass: try `omega` for all arithmetic-looking obligations
2. Build once, check which succeeded
3. Second pass: try `simp` variants for remaining `sorry`s
4. Build again
5. Third pass: try `decide` or `aesop` for remaining
6. Final build

#### 6c. Timeout Handling

`lake build` can be slow, especially with Mathlib. Set a reasonable
timeout:

```bash
timeout 120 lake build 2>&1
```

If the build times out, report it and keep all remaining `sorry`
markers. Do not retry indefinitely.

### 7. Report Results

After generating and attempting to discharge proofs, report
a summary.

#### 7a. Obligation Table

```markdown
## Proof Obligations

**Specification**: docs/account.tex
**Lean project**: proofs/

| # | Obligation | Status | Tactic |
|---|-----------|--------|--------|
| 1 | init_establishes_invariant | proved | omega |
| 2 | deposit_preserves_invariant | sorry | - |
| 3 | withdraw_preserves_invariant | proved | simp; omega |
| 4 | close_preserves_invariant | sorry | - |
```

#### 7b. Summary Counts

```markdown
### Summary

- **Total obligations**: 4
- **Proved**: 2
- **Remaining (sorry)**: 2
- **Proof coverage**: 50%
```

#### 7c. Build Status

Report the final `lake build` output:

```markdown
### Build Status

`lake build` completed successfully (exit code 0).
All generated Lean files are syntactically valid.
```

Or if there were issues:

```markdown
### Build Status

`lake build` reported errors:

- `State.lean:15: type mismatch ...`

These errors need manual correction. The generated files are
a starting point — review the type mappings and adjust as needed.
```

#### 7d. Next Steps

Suggest concrete next steps based on the results:

- If all obligations are proved: "All proof obligations discharged.
  The specification's invariant is mechanically verified."
- If some remain: "To discharge remaining obligations, open
  `proofs/ZSpec/Proofs/Preserves.lean` in VS Code with the
  Lean 4 extension and work through each `sorry` interactively."
- If build failed: "Fix the build errors first, then attempt
  proof discharge with `lake build` from the `proofs/` directory."

### 8. File Update Policy

When regenerating proofs for a specification that already has
a `proofs/` directory:

- **Never overwrite** files that have had `sorry` replaced with
  real proofs. Check each theorem: if the body is not `sorry`,
  preserve it.
- **Add new obligations** for operations that were added to the spec.
- **Remove stale obligations** for operations that were deleted
  from the spec (comment them out with a note, do not delete).
- **Update signatures** if the operation's type changed, but
  preserve proof bodies where possible and mark with
  `-- TODO: proof may need updating` if the signature changed.

## Error Handling

| Error | Response |
|-------|----------|
| Lean not installed | "Lean 4 is not installed. Run `/z-spec:setup lean` to install via elan." |
| Lake not installed | "Lake not found. It should be included with Lean 4. Run `elan toolchain install leanprover/lean4:v4.16.0`." |
| Specification not found | "No Z specification found. Specify path or create one with `/z-spec:code2model`." |
| No state schemas | "No state schemas with invariants found. Nothing to prove." |
| No operations | "No operation schemas found. Generating only init obligation." |
| `lake update` fails | "Failed to fetch Lean dependencies. Check network connection. Try `--no-mathlib` for a standalone project." |
| `lake build` fails | Show errors, suggest fixes, keep `sorry` markers. |
| `lake build` timeout | "Build timed out after 120s. Mathlib builds can be slow on first run. Try `cd proofs && lake build` manually." |
| Parse error in schema | "Could not parse schema {name}. Skipping." (continue with others) |
| Unsupported Z construct | "Z construct {construct} has no direct Lean translation. Modeling as `sorry` placeholder." |

## Worked Example

Given this Z specification (`docs/counter.tex`):

```latex
\begin{zed}
[COUNTERID]
\end{zed}

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
```

The command generates:

**proofs/ZSpec/Basic.lean**:

```lean
import Mathlib.Data.Finset.Basic
import Mathlib.Tactic

opaque CounterId : Type

def MAX_COUNT : Nat := 100
```

**proofs/ZSpec/State.lean**:

```lean
import ZSpec.Basic

structure Counter where
  value : Nat
  limit : Nat
  deriving Repr

def Counter.invariant (s : Counter) : Prop :=
  s.value <= s.limit /\ s.limit <= MAX_COUNT
```

**proofs/ZSpec/Operations.lean**:

```lean
import ZSpec.State

def initCounter : Counter :=
  { value := 0, limit := MAX_COUNT }

def increment_precondition (s : Counter) : Prop :=
  s.value < s.limit

def increment (s : Counter) : Counter :=
  { s with value := s.value + 1 }

def reset_precondition (s : Counter) : Prop := True

def reset (s : Counter) : Counter :=
  { s with value := 0 }
```

**proofs/ZSpec/Proofs/InitEstablishes.lean**:

```lean
import ZSpec.Operations

theorem init_establishes_invariant :
    initCounter.invariant := by
  unfold Counter.invariant initCounter MAX_COUNT
  omega
```

**proofs/ZSpec/Proofs/Preserves.lean**:

```lean
import ZSpec.Operations

theorem increment_preserves_invariant
    (s : Counter)
    (h_inv : s.invariant)
    (h_pre : increment_precondition s) :
    (increment s).invariant := by
  unfold Counter.invariant increment increment_precondition at *
  omega

theorem reset_preserves_invariant
    (s : Counter)
    (h_inv : s.invariant)
    (h_pre : reset_precondition s) :
    (reset s).invariant := by
  unfold Counter.invariant reset at *
  omega
```

Report:

```
## Proof Obligations

| # | Obligation | Status | Tactic |
|---|-----------|--------|--------|
| 1 | init_establishes_invariant | proved | unfold; omega |
| 2 | increment_preserves_invariant | proved | unfold; omega |
| 3 | reset_preserves_invariant | proved | unfold; omega |

### Summary

- Total obligations: 3
- Proved: 3
- Remaining (sorry): 0
- Proof coverage: 100%
```

## Integration with Other Commands

### With /z-spec:check

Always type-check the specification before generating proofs.
`/z-spec:check` validates Z syntax; `/z-spec:prove` validates
semantic properties.

### With /z-spec:partition

`/z-spec:partition` derives test cases; `/z-spec:prove` derives
proof obligations. They are complementary: tests give confidence
through enumeration, proofs give certainty through deduction.
A proved obligation means no test is needed for that property.

### With /z-spec:model2code

`/z-spec:model2code` generates implementation code.
`/z-spec:prove` generates formal proofs about the specification.
Together they provide both executable code and verified
correctness guarantees.

## Reference

- Z notation syntax: `reference/z-notation.md`
- Schema patterns: `reference/schema-patterns.md`
- Lean 4 type mappings: `reference/lean4-patterns.md`
