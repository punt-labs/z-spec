---
paths:
  - "**/*.py"
---

# Object-Oriented Design Requirements

These rules close the gap between "code that passes style checks" and "code
that is actually object-oriented." They prevent procedural codebases that
technically satisfy all other rules.

## PY-OO-1: Domain Entities Must Be Classes

**Statement**: Every noun in the domain that has both data and behavior must be
modeled as a class with private state and methods. Functions operating on the
same data structure are a code smell — that data and those functions belong in
a class together.

**Symptoms of violation**:
- A `dict` or `TypedDict` passed through 3+ functions as the first argument
- A module with 5+ functions that all take the same parameter type
- Data created in one function and mutated in another via return values

**Criterion**:
- Pass: domain concepts (User, Listing, Bid, etc.) are classes with encapsulated state
- Fail: domain logic lives in top-level functions operating on raw data structures

**Tooling**:
- Heuristic: `grep -c "^def " module.py` vs `grep -c "class " module.py` —
  ratio > 5:1 in a domain module is a red flag
- AST check: functions with 4+ parameters of the same TypedDict type → flag
- LLM review: "Could these functions be methods on a class?"

## PY-OO-2: Module Size and Cohesion Limits

**Statement**: A single module should contain at most 2-3 closely related
classes (e.g., a class and its iterator, or a base class and its immediate
subclasses). A module exceeding 300 lines likely violates SRP and should be
split.

**Exception**: Standalone scripts with `if __name__ == "__main__":` (CLI tools,
one-off utilities) may exceed 300 lines if all classes in the module collaborate
directly and the module has no external consumers. The threshold targets library
modules where SRP and importability matter, not self-contained programs.

**Criterion**:
- Pass: each module has 1-3 classes; module < 300 lines; all classes in the
  module collaborate directly
- Pass (exception): standalone script > 300 lines with `__main__` guard, ≤ 3
  collaborating classes, no external importers
- Fail: module has 5+ unrelated classes; module > 500 lines; classes in the
  module don't reference each other

**Tooling**:
- `wc -l module.py` — flag if > 300
- AST check: count `ClassDef` nodes per module — flag if > 3
- Grep: classes in module that don't reference each other → split candidates
- Exception check: `grep -l "if __name__" module.py` — standalone scripts get
  relaxed threshold of 500 lines

## PY-OO-3: Function Parameter Count Limit

**Statement**: A function or method with more than 4 positional parameters
(excluding `self`/`cls`) is a sign that its parameters should be grouped into
an object. Use a class, dataclass, or TypedDict to bundle related parameters.

**Exception**: `**kwargs` with `Unpack[TypedDict]` is acceptable for Builder
pattern setters.

**Criterion**:
- Pass: methods have <= 4 positional parameters
- Fail: method signature has 5+ positional parameters

**Tooling**:
- AST check: count `ast.arg` nodes in function signatures (exclude self/cls)
- ruff: `PLR0913` (too-many-arguments) — set max-args = 4
- `ruff check --select PLR0913`

## PY-OO-4: No Raw Data Structures for Domain Concepts

**Statement**: Do not use `dict`, `list`, `tuple`, or `TypedDict` as the primary
representation of a domain concept that has behavior. These are acceptable as
internal implementation details of a class, but not as the public interface for
domain entities.

**When TypedDict IS appropriate**: for snapshot/memento data, for kwargs typing,
for serialization boundaries.
**When TypedDict is NOT appropriate**: as a substitute for a class that should
have methods, validation, and invariants.

**Criterion**:
- Pass: domain entities are classes; TypedDicts used only for data transfer
- Fail: `TypedDict` with 5+ fields passed through multiple functions that
  mutate it

**Tooling**:
- LLM review: TypedDicts that appear in 3+ function signatures → should be a class
- AST check: TypedDict usage outside of `TYPE_CHECKING` blocks and internal state

## PY-OO-5: State + Behavior = Class

**Statement**: When you find yourself writing a function that (a) takes a data
structure, (b) reads multiple fields from it, and (c) returns a modified version,
that function should be a method on a class that owns that data.

This is the fundamental OO design heuristic: data and the operations on that
data belong together.

**Symptoms requiring refactoring to a class**:
- `def activate(listing: dict) -> dict` — this should be `listing.activate()`
- `def total_price(items: list[dict]) -> Decimal` — this should be on a
  collection class
- Multiple functions importing and operating on the same TypedDict

**Criterion**:
- Pass: operations on data are methods of the class owning that data
- Fail: functions reach into other objects' data to perform logic

**Tooling**:
- LLM review: "Does this function access another object's internal state?"
- Heuristic: function body with 3+ accesses to fields of its first parameter →
  candidate for method extraction

## PY-OO-6: Recognize When Patterns Apply

**Statement**: The design patterns in PY-DP-1 through PY-DP-11 are not optional
decorations — they are mandatory when their trigger condition is met. An agent
must actively identify these conditions:

| Trigger | Required Pattern |
|---------|-----------------|
| Object caching for immutable values | Flyweight (PY-DP-1) |
| One class owns another's creation data | Factory (PY-DP-2) |
| Object that changes behavior by state | State Pattern (PY-DP-3) |
| Object data set incrementally | Builder (PY-DP-4) |
| Undo/restore needed | Memento (PY-DP-5) |
| Clone with different identity | Prototype (PY-DP-6) |
| Exactly one global instance | Singleton (PY-DP-7) |
| Loose coupling between event and handler | PubSub (PY-DP-8) |
| "Do nothing" stand-in for an interface | Null Object (PY-DP-9) |
| Single entry point to a subsystem | Facade (PY-DP-10) |
| Interface with exactly one abstract method | Single-Method Interface (PY-DP-11) |

**Criterion**:
- Pass: trigger condition met → pattern applied
- Fail: trigger condition present but pattern not recognized or applied

**Tooling**:
- LLM review with explicit checklist: "For each class, does any trigger apply?"
- This cannot be automated — it requires domain understanding

## PY-OO-7: No Fake OO — Helpers in the Same Module as a Class Are Missing Methods

**Statement**: A module that defines a class AND a cluster of module-level
helper functions is procedural code wearing OO clothing. If a helper function
shares vocabulary or parameters with the class — operates on its types, builds
its instances, formats its errors — it is almost certainly a missing method on
the class.

**The smell**: `oo_score.py` flags it numerically as `method_ratio < 0.8` and
`class_to_func_ratio < 0.5`. This rule names the design pattern those metrics
detect so an author can recognize and prevent it instead of catching it after
the fact.

**Trigger conditions** — any one of these is the smell:

1. **The helper takes the class as a parameter.** `def _build_circle(d:
   Mapping[str, object]) -> CircleCmd: ...` should be `CircleCmd.from_wire`.
2. **The helper takes the same context tuple the class takes.** Five free
   functions that all start with `(kind: str, field: str, index: int)` →
   bundle into a `Context` value class with those as methods (PY-OO-3 +
   PY-OO-5).
3. **The helper returns the class.** Anything producing instances of `X` is
   either a constructor (move into `X.__new__` or a classmethod), a factory
   pattern (PY-DP-2), or a parser (`X.from_wire`).
4. **The helper operates on the class's fields.** `def merge_colors(a: Color,
   b: Color) -> Color: ...` should be `Color.merged_with(self, other) -> Color`.

**Rationale**: Default Python — what an agent or first-draft author produces —
emits free functions next to dataclasses because the LLM training corpus has
seen procedural Python ten times more than OO Python. The fact that a class
exists in the module is not enough; the methods of the class have to actually
own the operations. Otherwise the class is a glorified C struct and the module
is a pile of functions that happen to share a file.

**The legitimate exceptions** — module-level helpers ARE appropriate when:

- The function is genuinely standalone — same input/output, no shared vocabulary
  with any class in the module. Example: a `hash_bytes(b: bytes) -> str` utility
  in a crypto module.
- The function predates any class it touches in the import order (a class can't
  call a method on itself before its body executes; some module-init helpers
  qualify).
- The module is explicitly a "primitives" module — a small toolkit of stateless
  utilities used across many classes elsewhere (e.g., `text_utils.py` with
  `slugify`, `truncate_middle`). The Single Responsibility Principle (PY-IC-6)
  is satisfied because there are no classes in the module that the functions
  *should* belong to.

**Examples — bad**:

```python
# draw_wire.py — fake OO
def coerce_number(raw: object) -> float | None:    # ← orbits Thickness/Radius/Rounding
    ...

def object_sequence(raw: object) -> tuple[object, ...] | None:   # ← orbits Point2/PolylineCmd
    ...

@dataclass(frozen=True, slots=True)
class WireContext:                                  # ← real class, only 4 methods
    kind: str
    index: int | None
    def field_error(self, ...): ...
    def require_field(self, ...): ...
    ...
```

The two free functions take the same kinds of values WireContext operates on.
They should be methods.

**Examples — good**:

```python
# draw_wire.py — methods on the class that owns the vocabulary
@dataclass(frozen=True, slots=True)
class WireContext:
    _prefix: str
    @classmethod
    def for_indexed(cls, kind: str, index: int) -> Self: ...
    def require_number(self, raw: object, field: str) -> float: ...
    def require_sequence(self, raw: object, field: str) -> tuple[object, ...]: ...
    def require_string(self, raw: object, field: str) -> str: ...
    def require_field(self, d: Mapping[str, object], field: str) -> object: ...
    def field_error(self, field: str, expected: str, value: object) -> ValueError: ...

# Zero free functions in the module. Every operation lives on the class.
```

**Criterion**:
- Pass: every module that defines a class has zero free functions OR every
  free function passes the "legitimate exception" test above.
- Fail: a module has a class + ≥ 2 free functions that share parameters or
  return types with the class.

**Tooling**:
- Primary numeric: `oo_score.py` — `method_ratio >= 0.8` and
  `class_to_func_ratio >= 0.5` per file.
- AST recipe: in any module where `count(ClassDef) >= 1`, list every
  `FunctionDef` at module scope; for each, check whether its parameter or
  return types reference any class defined in the same module. Each hit is a
  candidate violation.
- LLM review: for each free function in a class-defining module, ask "is this
  a method of the class in disguise?" If the function takes the class as a
  parameter, takes the class's context tuple, returns the class, or operates
  on the class's fields, the answer is yes.

**Relation to other rules**:
- PY-OO-1 ("Domain entities must be classes") forbids representing a domain
  entity as a dict + functions. PY-OO-7 forbids the next-level mistake: a
  class + functions, where the functions should be the class's methods.
- PY-OO-5 ("State + Behavior = Class") tells you which functions should
  become methods (those that operate on a data structure's fields). PY-OO-7
  generalises: any helper near a class is suspect until proven independent.
- PY-IC-1 (composition over inheritance) is what helps you keep the class's
  surface small even as you absorb the helpers as methods — helpers that
  share state become a composed value class, not a base class.
