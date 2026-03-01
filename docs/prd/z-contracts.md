# PRD: /z-spec:contracts

## Problem

A type-checked, model-checked, even Lean-proven Z specification provides
no runtime protection. The spec lives in `.zed` files and proof artifacts;
the running code has no awareness of the invariants, preconditions, or
postconditions the spec defines.

Code can diverge silently from the spec during development. A developer
changes a field type, reorders a condition, or forgets a frame condition,
and nothing fails until a user hits the edge case in production. Tests
catch specific scenarios; nothing catches arbitrary violations at runtime.

This is the **enforcement gap**: the spec is verified, the tests pass,
but the running code has no guardrails derived from the spec itself.

## Solution

A new `/z-spec:contracts` command that generates precondition,
postcondition, and invariant assertion functions in the target language
(Swift, TypeScript, Python, Kotlin) directly from Z schemas.

For each state schema, the command generates:

- **`assertStateInvariant(state)`** -- checks all invariant predicates
  from the schema's `\where` block
- **`assertOpPrecondition(state, inputs)`** -- checks preconditions
  before each operation
- **`assertOpPostcondition(before, after, inputs)`** -- checks effects
  and frame conditions after each operation
- **Optional wrapper functions** (`--wrap`) that sandwich the real
  operation implementation with pre/post assertions

Assertions are designed for test and dev builds. They throw or assert
on violation, with a message identifying which predicate failed and
the concrete values that violated it.

## Scope

### In Scope

- New `commands/contracts.md` skill prompt
- Assertion code generation for Swift, TypeScript, Python, Kotlin
- `--wrap` flag for operation wrapper generation
- `--strip` flag to emit no-op stubs for production builds
- Language auto-detection (reuses model2code's detection)
- Predicate-to-expression translation for target language
- Frame condition checks (unchanged variables verified in postcondition)
- Clear violation messages with predicate name and failing values
- Updates to `commands/help.md` and `README.md`

### Out of Scope

- Production instrumentation or monitoring integration
- Performance overhead measurement or optimization
- Code modification of existing implementation files
- Aspect-oriented or decorator-based injection
- Changes to existing commands beyond help updates

## Predicate Translation

| Z Construct | Generated Assertion |
|-------------|---------------------|
| `x \in \nat` | `assert(x >= 0)` |
| `x < LIMIT` | `assert(x < LIMIT)` |
| `x \in \dom f` | `assert(f.has(x))` |
| `\#s \leq MAX` | `assert(s.count <= MAX)` |
| `x' = x + 1` | `assert(after.x == before.x + 1)` |
| `y' = y` (frame) | `assert(after.y == before.y)` |

## User Workflow

```text
/z-spec:code2model     -> create spec from code
/z-spec:check          -> verify spec is well-typed
/z-spec:test           -> verify spec is internally consistent
/z-spec:prove          -> prove properties universally
/z-spec:partition      -> derive required test cases from spec
/z-spec:contracts      -> generate runtime assertions from spec  <-- NEW
/z-spec:audit          -> verify tests exist in codebase
```

The contracts command sits after specification and before deployment,
providing runtime enforcement that bridges the spec-implementation gap.

## Success Criteria

- For any Z spec with state schemas and operations, generates
  compilable assertion functions in the target language
- Invariant assertions check every predicate from the state schema
- Precondition assertions check every predicate from the operation's
  `\where` block that references only pre-state and inputs
- Postcondition assertions check every predicate referencing post-state,
  including frame conditions for unmentioned variables
- Violation messages identify the specific predicate and failing values
- `--wrap` generates callable wrappers that assert before and after
  delegating to the real operation
- Generated code compiles without modification in the target language
