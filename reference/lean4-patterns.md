# Lean 4 Translation Patterns

Patterns for translating Z specifications to Lean 4 with Mathlib.

## Type Mappings

| Z Type | Lean 4 Type | Mathlib Import |
|--------|-------------|----------------|
| `\nat` | `Nat` | (built-in) |
| `\nat_1` | `Nat` (with `0 < n`) | (built-in) |
| `\num` | `Int` | (built-in) |
| `\power X` | `Finset X` or `Set X` | `Mathlib.Data.Finset.Basic` |
| `\finset X` | `Finset X` | `Mathlib.Data.Finset.Basic` |
| `X \pfun Y` | `X -> Option Y` | (built-in) |
| `X \fun Y` | `X -> Y` | (built-in) |
| `X \rel Y` | `Finset (X × Y)` | `Mathlib.Data.Finset.Basic` |
| `\seq X` | `List X` | (built-in) |
| `\seq_1 X` | `List X` (with `s != []`) | (built-in) |
| `X \cross Y` | `X × Y` | (built-in) |
| `\emptyset` | `{}` or `Finset.empty` | `Mathlib.Data.Finset.Basic` |
| `ZBOOL` | `Bool` or custom inductive | (built-in) |

## Free Types to Inductive

Z free types become Lean 4 `inductive` types.

### Z

```latex
\begin{zed}
Status ::= pending | active | suspended | closed
\end{zed}
```

### Lean 4

```lean
inductive Status where
  | pending
  | active
  | suspended
  | closed
  deriving DecidableEq, Repr
```

`DecidableEq` is required for `if` conditions and `Finset` membership.
`Repr` enables `#eval` debugging.

## Given Sets

Z given sets (`[X]`) declare abstract types with no internal structure.

```latex
\begin{zed}
[USERID, SESSIONID]
\end{zed}
```

```lean
-- opaque: truly abstract type
opaque UserId : Type
opaque SessionId : Type

-- variable: generic over carrier type (for reusable proofs)
variable {UserId : Type} [DecidableEq UserId]
```

## Schema to Structure

A Z state schema becomes a Lean 4 `structure` plus an invariant predicate.

### Z

```latex
\begin{schema}{Account}
balance : \nat \\
status : Status
\where
status = active \implies balance \geq 0
\end{schema}
```

### Lean 4

```lean
structure Account where
  balance : Nat
  status : Status

def Account.inv (s : Account) : Prop :=
  s.status = Status.active -> s.balance >= 0
```

Wrap the structure with its invariant using a subtype:

```lean
def ValidAccount := { s : Account // Account.inv s }
```

## Init Schemas

Init schemas become definitions returning the initial state.

### Z

```latex
\begin{schema}{InitAccount}
Account'
\where
balance' = 0 \\
status' = pending
\end{schema}
```

### Lean 4

```lean
def initAccount : Account :=
  { balance := 0, status := Status.pending }
```

## Operations

Delta schemas become state-transforming functions. Xi schemas become read-only.

### Z -- Delta operation

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

### Lean 4 -- Delta operation

```lean
def deposit (s : Account) (amount : Nat) (h_pos : 0 < amount)
    (h_pre : s.status = Status.active) : Account :=
  { balance := s.balance + amount, status := s.status }
```

Preconditions appear as hypothesis parameters. The caller must supply proofs.

### Z -- Xi operation (read-only)

```latex
\begin{schema}{GetBalance}
\Xi Account \\
result! : \nat
\where
result! = balance
\end{schema}
```

### Lean 4 -- Xi operation

```lean
def getBalance (s : Account) : Nat :=
  s.balance
```

## Proof Obligations

Three proof obligations arise from every Z specification.

### 1. Init establishes invariant

The initial state satisfies the state invariant.

```lean
theorem init_establishes_inv : Account.inv initAccount := by
  unfold Account.inv initAccount
  intro h
  contradiction
```

### 2. Operation preserves invariant

```lean
theorem deposit_preserves_inv (s : Account) (amount : Nat)
    (h_pos : 0 < amount)
    (h_pre : s.status = Status.active)
    (h_inv : Account.inv s) :
    Account.inv (deposit s amount h_pos h_pre) := by
  unfold Account.inv deposit
  simp [h_pre]
  exact h_inv h_pre
```

### 3. Precondition satisfiable

There exists a valid state in which the precondition holds.

```lean
theorem deposit_precondition_satisfiable :
    ∃ s : Account, Account.inv s ∧ s.status = Status.active := by
  exact ⟨{ balance := 0, status := Status.active },
         fun _ => Nat.zero_le _, rfl⟩
```

## Common Tactics

| Tactic | Use Case |
|--------|----------|
| `omega` | Linear arithmetic over `Nat` and `Int` |
| `simp` | Simplify using lemma database |
| `simp [h]` | Simplify with additional hypothesis `h` |
| `decide` | Decide finite propositions (enums, small `Nat`) |
| `intro h` | Introduce hypothesis from `->` or `forall` |
| `cases h` | Case split on inductive or disjunction |
| `constructor` | Split conjunction or provide `And.intro` |
| `exact e` | Provide exact proof term |
| `unfold f` | Unfold definition of `f` |
| `contradiction` | Close goal when hypotheses are contradictory |
| `rfl` | Prove `x = x` |
| `rw [h]` | Rewrite using equation `h` |
| `have h := ...` | Introduce intermediate fact |

### Tactic examples

```lean
example (n : Nat) (h : n >= 5) : n + 3 >= 8 := by omega
example : Status.pending != Status.active := by decide
example (s : Status) : s = Status.pending ∨ s = Status.active
    ∨ s = Status.suspended ∨ s = Status.closed := by cases s <;> simp
```

## Imports

| Z Construct | Mathlib Import |
|-------------|----------------|
| `\finset`, `\power` | `Mathlib.Data.Finset.Basic` |
| `\pfun` (partial function) | `Mathlib.Data.PFun` |
| `#` (cardinality) | `Mathlib.Data.Finset.Card` |
| `\nat` arithmetic proofs | (built-in since Lean 4.3.0) |
| `\num` (integers) | `Mathlib.Data.Int.Basic` |
| `\seq` (sequences as lists) | `Mathlib.Data.List.Basic` |
| `\dom`, `\ran` | `Mathlib.Order.RelClasses` |
| `\rel` (relations) | `Mathlib.Data.Finset.Prod` |

Most small specs only need:

```lean
import Mathlib.Data.Finset.Basic
import Mathlib.Tactic.Omega
import Mathlib.Tactic.Decide
```

## Project Structure

### Directory layout

```text
MySpec/
  lakefile.toml
  lean-toolchain
  MySpec/
    Basic.lean          -- free types, given sets
    State.lean          -- state schemas, invariants
    Operations.lean     -- operation definitions
    Proofs.lean         -- proof obligations
  MySpec.lean           -- root import file
```

### lean-toolchain

```text
leanprover/lean4:v4.16.0
```

### lakefile.toml

```toml
[package]
name = "MySpec"
version = "0.1.0"
leanOptions = [["autoImplicit", false]]

[[lean_lib]]
name = "MySpec"

[[require]]
name = "mathlib"
scope = "leanprover-community"
rev = "main"
```

> Pin `rev` to a specific Mathlib commit SHA for reproducible builds
> that match your `lean-toolchain` version.

Set `autoImplicit = false` to prevent accidental free variables.

## ZBOOL Mapping

The ProB-compatible `ZBOOL` free type maps directly to a Lean 4 inductive.

### Z

```latex
\begin{zed}
ZBOOL ::= ztrue | zfalse
\end{zed}
```

### Lean 4

```lean
inductive ZBool where
  | ztrue
  | zfalse
  deriving DecidableEq, Repr
```

Or use `abbrev ZBool := Bool` when the spec does not need a custom type.

## Partial Functions

Z partial functions (`\pfun`) map to `X -> Option Y` for simple cases, or
`Finmap` when cardinality constraints are needed:

```lean
-- Simple: X \pfun Y
structure Registry where
  accounts : UserId -> Option Account

-- With cardinality bound: use Finmap
import Mathlib.Data.Finmap

structure Registry where
  accounts : Finmap (fun (_ : UserId) => Account)

def Registry.inv (r : Registry) : Prop :=
  r.accounts.card <= 1000
```
