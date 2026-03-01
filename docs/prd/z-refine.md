# PRD: /z-spec:refine

## Problem

Even with testing, runtime contracts, and proofs, there is no formal
link between the abstract Z specification and the concrete implementation.
The abstraction gap -- how database rows map to partial functions, how
string status codes map to free types, how array indices map to sequence
positions -- is where bugs live.

A developer can prove the abstract spec correct and test the concrete
code thoroughly, yet the two may disagree because the mapping between
them was never verified. The abstraction function exists only in the
developer's head, untested and unformalized.

This is the **refinement gap**: the spec is correct, the code works
for known inputs, but the semantic correspondence between abstract
and concrete has no verification whatsoever.

## Solution

A new `/z-spec:refine` command that implements the Z data refinement
technique (Woodcock & Davies, Chapter 14). The user defines an
abstraction function mapping concrete implementation state to abstract
Z state. The command generates commutativity tests for every operation
and optionally generates Lean 4 proofs of the refinement conditions.

For each operation, refinement requires that this diagram commutes:

```text
Concrete --concreteOp--> Concrete'
   |                        |
 abstract                abstract
   |                        |
Abstract --abstractOp--> Abstract'
```

That is: `abstract(concreteOp(c)) = abstractOp(abstract(c))` for all
valid concrete states `c`.

## What It Generates

1. **Abstraction function scaffold** -- guided definition mapping
   concrete types to abstract Z types, with prompts for each field
2. **Init commutativity test** -- verifies that `abstract(concreteInit)`
   satisfies the abstract initial state schema
3. **Operation commutativity tests** -- for every operation, verifies
   the diagram commutes using both concrete and property-based inputs
4. **Optional Lean 4 commutativity theorems** -- formal proofs that
   each operation commutes with the abstraction function

## Scope

### In Scope

- New `commands/refine.md` skill prompt
- Abstraction function scaffold generation (Swift, TypeScript, Python,
  Kotlin) with guided prompts for each state field mapping
- Commutativity test generation for init and all operations
- Property-based commutativity tests using random inputs
- Optional `--lean` flag for Lean 4 refinement proof generation
- Applicability correctness: preconditions lift through abstraction
- Updates to `commands/help.md` and `README.md`

### Out of Scope

- Automated abstraction function inference or synthesis
- Forward simulation (implementation derives from spec top-down)
- Downward simulation (for non-functional refinements)
- Schema refinement (only data refinement)
- Changes to existing commands beyond help updates

## Refinement Conditions

For each operation, three conditions must hold:

### 1. Init Commutativity

```text
abstract(concreteInit) satisfies AbstractInit
```

The concrete initial state, when abstracted, satisfies the abstract
initial state schema.

### 2. Applicability

```text
AbstractPre(abstract(c)) => ConcretePre(c)
```

If the abstract precondition holds for the abstracted state, the
concrete precondition holds for the concrete state.

### 3. Correctness

```text
abstract(concreteOp(c)) = abstractOp(abstract(c))
```

Applying the concrete operation and then abstracting gives the same
result as abstracting first and then applying the abstract operation.

## User Workflow

```text
/z-spec:code2model     -> create spec from code
/z-spec:check          -> verify spec is well-typed
/z-spec:test           -> verify spec is internally consistent
/z-spec:prove          -> prove properties universally
/z-spec:partition      -> derive required test cases from spec
/z-spec:contracts      -> generate runtime assertions
/z-spec:refine         -> verify data refinement correctness      <-- NEW
/z-spec:audit          -> verify tests exist in codebase
```

The refine command sits at the end of the verification pipeline,
providing the final link between abstract specification and concrete
implementation.

## Success Criteria

- For a spec, implementation, and user-defined abstraction function,
  generates commutativity tests for every operation
- Init commutativity test verifies the concrete initial state abstracts
  to a valid abstract initial state
- Operation commutativity tests detect when the diagram fails to commute
- Property-based tests exercise commutativity with random valid inputs
- `--lean` generates Lean 4 theorems stating the refinement conditions
  with `sorry` placeholders, and `lake build` succeeds
- Failing commutativity tests report the concrete state, the two
  abstract states (via abstraction before/after), and which operation
  caused divergence
