# PRD: /z-spec:prove

## Problem

The z-spec plugin can verify a Z specification is well-typed (via fuzz)
and can animate bounded state spaces (via probcli model-checking). However,
neither tool can prove that properties hold **universally** — for all possible
inputs and all reachable states.

- **fuzz** checks types only. It confirms `balance : \nat` but cannot verify
  that `Deposit` preserves `balance \geq 0`.
- **probcli** explores finite state spaces. With `DEFAULT_SETSIZE 2` and
  bounded integers, it checks hundreds to thousands of states. It cannot
  guarantee properties for unbounded domains.

This is the **proof gap**: the spec is type-correct and consistent within
small bounds, but nothing machine-checks that invariants hold universally
or that operations are correct for all valid inputs.

## Solution

A new `/z-spec:prove` command that translates Z specifications into
**Lean 4** proof obligations, generating a complete Lean project with:

1. **Structure definitions** for each state schema
2. **Invariant predicates** from schema `\where` blocks
3. **Operation functions** from Delta/Xi schemas
4. **Proof obligation theorems** with `sorry` placeholders:
   - `Init` establishes invariant
   - Each operation preserves invariant (given precondition)
   - Precondition satisfiability (optional)

The user (or an AI prover) fills in the `sorry` markers. Running
`lake build` reports which obligations are discharged vs. which remain.

## Why Lean 4

Lean 4 is the actively developed version, used by Terence Tao (PFR
conjecture, Analysis I formalization) and the broader formalization
community. Key advantages:

- **Mathlib4**: 210,000+ formalized theorems; `Nat`, `Int`, `Finset`,
  `Set`, `List`, `Multiset` all available with rich tactic support
- **omega tactic**: Solves linear arithmetic over `Nat`/`Int` automatically
- **decide tactic**: Handles decidable propositions
- **simp tactic**: Powerful simplification with Mathlib lemmas
- **Lake build system**: Reproducible builds with dependency management
- **elan**: Toolchain manager (like rustup) for easy installation

## Scope

### In Scope

- New `commands/prove.md` and `commands/prove-dev.md` skill prompts
- New `reference/lean4-patterns.md` reference file for Z-to-Lean mappings
- Lean 4 project generation (lakefile.toml, lean-toolchain, .lean files)
- Type mappings: Z types to Lean 4 types (with Mathlib)
- Proof obligation generation for init + operations
- Integration with `/z-spec:setup` (elan/lean/lake installation)
- Integration with `/z-spec:doctor` (lean/lake health checks)
- Updates to `commands/help.md` and `README.md`

### Out of Scope

- Automated proof completion (users fill `sorry` markers)
- Refinement proofs (concrete refines abstract)
- Schema calculus translation (schema conjunction, piping)
- Lean 4 IDE integration (VS Code extensions)
- Changes to existing commands beyond help/setup/doctor

## Z-to-Lean 4 Type Mappings

| Z Construct | Lean 4 Type | Notes |
|-------------|-------------|-------|
| Given set `[X]` | `opaque X : Type` | Abstract type |
| Free type `T ::= a \| b` | `inductive T where \| a \| b` | With `DecidableEq` |
| `\nat` | `Nat` | Built-in |
| `\num` | `Int` | Built-in |
| `\nat_1` | `Nat` with `h : n > 0` | Positive subtype |
| `\power X` | `Set X` or `Finset X` | `Finset` for decidable |
| `X \pfun Y` | `X -> Option Y` | Partial function |
| `X \fun Y` | `X -> Y` | Total function |
| `\seq X` | `List X` | Finite sequence |
| `\bag X` | `Multiset X` | Mathlib multiset |
| `X \cross Y` | `X × Y` | Product type |
| `ZBOOL` | `Bool` | No B-keyword conflict in Lean |
| `x \mapsto y` | `(x, y)` | Pair in relation |
| `\dom f` | Domain definition | Via Mathlib or custom |
| `\ran f` | Range definition | Via Mathlib or custom |

## Proof Obligation Categories

For each Z specification, generate these proof obligations:

### 1. Initialization

```lean
theorem init_establishes_invariant :
    initState.invariant := by sorry
```

Proves: the initial state satisfies all state invariants.

### 2. Invariant Preservation (per operation)

```lean
theorem op_preserves_invariant (s : State) (input : InputType)
    (h_inv : s.invariant)
    (h_pre : op_precondition s input) :
    (op s input).invariant := by sorry
```

Proves: if the invariant holds and the precondition is met,
the operation produces a state where the invariant still holds.

### 3. Precondition Satisfiability (optional)

```lean
theorem op_precondition_satisfiable :
    ∃ (s : State) (input : InputType),
      s.invariant ∧ op_precondition s input := by sorry
```

Proves: the precondition is not vacuously true (there exist valid
inputs that satisfy it).

## User Workflow

```text
/z-spec:code2model     -> create spec from code
/z-spec:check          -> verify spec is well-typed
/z-spec:test           -> verify spec is internally consistent
/z-spec:prove          -> generate Lean 4 proof obligations     <-- NEW
/z-spec:partition      -> derive required test cases from spec
/z-spec:audit          -> verify those tests exist in codebase
```

The prove command sits between animation (bounded checking) and
testing (implementation verification), providing the missing
universal correctness guarantee.

## Success Criteria

- For any Z specification with state schemas and operations,
  `/z-spec:prove` generates a valid Lean 4 project
- `lake build` succeeds (with `sorry` warnings for unproven obligations)
- Generated structures correctly encode Z types and invariants
- Generated theorems correctly state the proof obligations
- Simple proof obligations (linear arithmetic) can be discharged
  with `omega`/`simp`/`decide` tactics
- `/z-spec:setup lean` installs elan, lean, and lake
- `/z-spec:doctor` reports lean/lake status

## Generated Project Structure

```text
proofs/
  lean-toolchain              # Pin Lean 4 version
  lakefile.toml               # Package config (depends on Mathlib)
  ZSpec/
    Basic.lean                # Imports, given sets, free types
    State.lean                # State schema structures + invariants
    Operations.lean           # Operation definitions
    Proofs/
      InitEstablishes.lean    # Init proof obligations
      Preserves.lean          # Operation preservation proofs
```
