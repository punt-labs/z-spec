---
paths:
  - "**/*.py"
---

# Type Safety Standards

## PY-TS-1: Deferred Annotations Required

**Statement**: Every module must begin with `from __future__ import annotations`.

**Rationale**: Enables PEP 563 postponed evaluation, allowing forward references
and avoiding circular import issues at runtime. Required until PEP 649 lands in 3.14.

**Criterion**:
- Pass: first non-comment import is `from __future__ import annotations`
- Fail: missing or placed after other imports

**Tooling**:
- Primary: `ruff check --select I001,FA100` (isort + future-annotations)
- AST check: `ast.parse` → verify first `ImportFrom` node is `__future__.annotations`
- mypy: catches some symptoms but not the import itself

## PY-TS-2: Full Annotation Coverage

**Statement**: Every function/method must have type annotations on all parameters
and the return type. Class-level instance attributes must be annotated.

**Criterion**:
- Pass: `mypy --strict` reports zero "missing annotation" errors
- Fail: any `error: Function is missing a type annotation` or similar

**Tooling**:
- Primary: `mypy --strict` (configured via `pyproject.toml` with `strict = true`)
- Alternative: `pyright --pythonversion 3.13` in strict mode

## PY-TS-3: Self Return Type on Constructors

**Statement**: `__new__` methods must return `-> Self` (from `typing`).
Fluent methods that return the instance must also return `-> Self`.

**Criterion**:
- Pass: all `__new__` signatures end with `-> Self`
- Fail: `__new__` returns `-> "ClassName"` or untyped

**Tooling**:
- Primary: `mypy --strict` (Self is enforced under strict)
- AST check: grep `def __new__` lines for `-> Self`

## PY-TS-4: Abstract Types from collections.abc

**Statement**: Import abstract types (`Hashable`, `Iterable`, `Iterator`,
`Mapping`, `Sequence`, `Callable`) from `collections.abc`, not from `typing`.

**Criterion**:
- Pass: no `from typing import Hashable/Iterable/Iterator/Mapping/Sequence`
- Fail: abstract collection types imported from `typing`

**Tooling**:
- Primary: `ruff check --select UP035` (deprecated-typing-imports)
- Grep: `grep -n "from typing import.*\(Hashable\|Iterable\|Iterator\|Mapping\|Sequence\)"`

## PY-TS-5: Modern Generic Syntax (PEP 695)

**Statement**: Use PEP 695 generic syntax (`class Foo[T: Bound]:`) instead of
`TypeVar` + `Generic[T]` when targeting Python 3.12+.

**Criterion**:
- Pass: generic classes use bracket syntax; no `TypeVar` for class-level generics
- Fail: `T = TypeVar("T"); class Foo(Generic[T])`

**Tooling**:
- Primary: `ruff check --select UP040` (non-pep695-generic)
- mypy: requires `enable_incomplete_feature = ["NewGenericSyntax"]` in config

## PY-TS-6: Protocol for Structural Interfaces, ABC for Shared Implementation

**Statement**: Use `Protocol` when defining a structural interface with no shared
implementation. Use `ABC` when the base class shares implementation code.

**Criterion**:
- Pass: interface-only types inherit from `Protocol`; classes sharing code inherit from `ABC`
- Fail: `ABC` used for pure interfaces; `Protocol` used with concrete method implementations

**Tooling**:
- Primary: LLM review (semantic distinction)
- Heuristic AST check: Protocol subclass with non-abstract method bodies > 1 line → warning

## PY-TS-7: TYPE_CHECKING Guard for Circular Imports

**Statement**: When importing a type from another module solely for annotations
and it would cause a circular import at runtime, import under
`if TYPE_CHECKING:` guard.

**Criterion**:
- Pass: circular import resolved via TYPE_CHECKING; no runtime ImportError
- Fail: runtime circular import error

**Tooling**:
- Primary: `mypy --strict` (catches missing types)
- Runtime: `python -c "import module"` succeeds without ImportError
- Grep: `grep -rn "if TYPE_CHECKING"` to audit existing guards

## PY-TS-8: Union Syntax and Literal Types

**Statement**: Use `X | Y` syntax (PEP 604) instead of `Optional[X]` or
`Union[X, Y]`. Use `Literal[...]` for constrained string/int values.

**Criterion**:
- Pass: no `Optional[X]` or `Union[X, Y]` in annotations
- Fail: old-style union syntax present

**Tooling**:
- Primary: `ruff check --select UP007` (non-pep604-annotation)

## PY-TS-9: No Any Without Documented Reason

**Statement**: Never use `Any` unless interfacing with an untyped third-party
library. Every `Any` must have an inline `# type: ignore[...]` or comment
explaining why it is unavoidable.

**Criterion**:
- Pass: zero `Any` in annotations, or each has a justifying comment
- Fail: bare `Any` without explanation

**Tooling**:
- Grep: `grep -Pn "\bAny\b" --include="*.py"` and verify each has comment
- ruff: `ANN401` (dynamically-typed-expression) flags `Any` in signatures
- `ruff check --select ANN401`

## PY-TS-10: No hasattr — Use Protocols

**Statement**: Never use `hasattr()` to check for attributes or methods. Use
`Protocol` classes and `isinstance()` checks against the protocol, or structural
typing via type annotations.

**Rationale**: `hasattr()` bypasses the type system and hides interface
requirements. Protocols make the required interface explicit and checkable.

**Criterion**:
- Pass: zero `hasattr()` calls in source code
- Fail: `hasattr(obj, "method")` used for type dispatch

**Tooling**:
- Grep: `grep -rn "hasattr(" --include="*.py"` — should return zero hits
- AST check: no `ast.Call` with `func.id == "hasattr"`

## PY-TS-11: No Runtime Introspection for Type Decisions

**Statement**: Do not use `type()`, `__class__`, or `inspect` to make branching
decisions about types. Use explicit protocol inheritance and `isinstance()`.

**Criterion**:
- Pass: type dispatch uses `isinstance()` against known classes/protocols
- Fail: `if type(x).__name__ == "Foo"` or `inspect.getmembers()` for dispatch

**Tooling**:
- Grep: `grep -Pn "type\(\w+\)\.__" --include="*.py"` — flag hits
- LLM review: any use of `inspect` module for type decisions

## PY-TS-12: cast() in String Form

**Statement**: Use `cast("TargetType", value)` with the type as a string, not
`cast(TargetType, value)`. This satisfies ruff TC006 and avoids importing the
type at runtime when it's only needed for the cast.

**Criterion**:
- Pass: all `cast()` calls use string form for the type argument
- Fail: `cast(SomeClass, value)` with a direct type reference

**Tooling**:
- Primary: `ruff check --select TC006`

## PY-TS-13: py.typed Marker in Every Package

**Statement**: Every package that ships type annotations must include an empty
`py.typed` marker file per PEP 561. This tells type checkers that the package
supports typed consumption.

**Criterion**:
- Pass: `src/<package>/py.typed` exists (empty file)
- Fail: typed package without `py.typed`

**Tooling**:
- Check: `test -f src/<package>/py.typed`
- mypy: warns when consuming a package without `py.typed`

## PY-TS-14: Type System Giving Up — Justify Every Optional, Any, and Raw Dict

**Statement**: Three annotation patterns are all symptoms of the same disease —
the author couldn't or wouldn't model the value precisely. Every occurrence
must have an inline justification comment explaining why the precise type is
infeasible. No justification → not allowed.

| Pattern | What it means |
|---------|---------------|
| `T \| None` | "I'm not committing to whether this exists." |
| `Any` | "I'm not committing to what shape this has." |
| `dict[str, Any]`, `list[Any]`, `dict[str, object]` at API boundaries | "I'm not committing to a schema." |

Each is a *deferred design decision*. The deferral has a cost: every caller has
to defensively handle the unknown, the type checker can't catch wrong-shape
data, and bugs surface far from their cause.

**Rationale**: the three patterns interact. A `dict[str, Any]` parameter forces
the implementation to use `dict.get(key, None)` (an Optional), and the only
honest annotation for `dict.get`'s return is `Any | None`. Banning one without
banning the others lets the same anti-pattern hop across symptoms.

**The justification gate**: every `| None` field, every `Any` annotation, every
`dict[str, Any]` / `list[Any]` parameter must be paired with an inline comment
naming the legitimate reason. Examples:

```python
# OK — absence is the documented contract; tooltip is genuinely optional UI state.
tooltip: str | None = None

# OK — third-party library has no type stubs (see PY-TS-9).
config: Any  # type: ignore[no-any-unimported]  # untyped_lib.Config

# OK — wire boundary; JSON deserialization yields object until narrowed.
def decode(self, raw: dict[str, object]) -> ScenePayload: ...
```

The "OK" cases share one trait: they document *why* the precise type is
infeasible right where the imprecision lives. Future readers (and future-you)
don't have to reverse-engineer the intent.

**Examples — bad**:

```python
def parse(text: str) -> Config | None:        # PY-EH-8 + PY-TS-14: raise or return Config
    ...

def merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:   # PY-OO-4 + PY-TS-14
    ...

class Element:
    color: str | None = None                  # is None a state or a default?
    style: dict[str, Any] | None = None       # what shape? unknown to types.
    metadata: Any = None                      # the type system gave up entirely.
```

**Examples — good**:

```python
def parse(text: str) -> Config:               # raises on bad input (PY-EH-8)
    ...

@dataclass(frozen=True, slots=True)
class MergeArgs:                              # the shape that was implicit becomes a class
    left: Config
    right: Config

def merge(args: MergeArgs) -> Config:
    ...

class Element:
    color: str = "#FFFFFF"                    # default is total, not absent
    style: Literal["body", "heading"] = "body"  # constrained, not Any
    # metadata: extracted into its own typed class — see [[MetadataBlock]]
```

**Criterion**:
- Pass: every `| None`, `Any`, `dict[str, Any]`, and `list[Any]` annotation has
  an inline justification comment on the same logical line or the line above.
- Fail: any of these patterns appears without justification.

**Tooling**:
- Grep audit recipes:

```bash
# field-typed Optionals — match both builtins (str, int, list, tuple, dict, …)
# and user types (Capitalized), including parameterised generics like list[X].
grep -Prn ":\s*[\w\[\], .]+\s*\|\s*None\b" --include="*.py" src/

# Optional return types
grep -Prn "->\s*[\w\[\], .]+\s*\|\s*None\b" --include="*.py" src/

# Any annotations
grep -Prn "\bAny\b" --include="*.py" src/

# Raw dict/list at API boundaries (Any-valued or unparameterised)
grep -Prn "dict\[str,\s*Any\]|list\[Any\]|\bdict\b(?!\[)|\blist\b(?!\[)" --include="*.py" src/
```

Each hit must have a justification comment. Bare hits fail the rule.

- LLM review: for each match, ask:
  1. "Is this absence documented as the function/field's contract?" (PY-EH-8 cross-check)
  2. "Could a `Literal[...]` / typed class / Protocol replace this?" (PY-OO-4 + PY-TS-8)
  3. "Is this a wire boundary where deserialization yields `object`?"
  If the answer to any is "yes" — fine, but write the comment. If "no" — the
  type needs to be made precise.

**Relation to other rules**:
- PY-TS-8 governs the *spelling* (`X | None`, not `Optional[X]`). PY-TS-14
  governs the *use*.
- PY-TS-9 already gates `Any`. PY-TS-14 extends the same gate to `| None` and
  raw dicts.
- PY-OO-4 forbids raw dicts as primary representation for domain entities.
  PY-TS-14 catches the cases where dicts slip into API boundaries.
- PY-EH-8 governs the runtime behavior of value-producing functions (raise,
  don't return None). PY-TS-14 governs the corresponding *annotation* — if the
  function would have returned `T | None`, PY-EH-8 says rewrite it; PY-TS-14
  ensures any remaining `T | None` is justified.
