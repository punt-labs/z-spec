---
paths:
  - "**/*.py"
---

# Class Construction Standards

## PY-CC-1: Use __new__ as the Constructor

**Statement**: Use `__new__` instead of `__init__` for class construction.
`__new__` controls instance creation; `__init__` merely initializes an
already-created instance.

**Rationale**: `__new__` is required for flyweight/singleton patterns (controlling
whether a new object is created), for `@final` classes, and for consistency with
the metaclass `type.__call__` dispatch. The instructor dedicates an entire lesson
(`xx-truth-about-constructors.py`) to this principle.

**Pattern**:
```python
def __new__(cls, ...) -> Self:
    self = super().__new__(cls)
    self._field = value
    return self
```

**Criterion**:
- Pass: classes use `__new__` with `super().__new__(cls)`, return `self`
- Fail: class defines `__init__` (exception: `@dataclass` which generates it)

**Tooling**:
- AST check: `grep -rn "def __init__" --include="*.py"` should return zero hits
  (excluding dataclasses and third-party code)
- Custom ruff rule or pylint checker for `__init__` presence

## PY-CC-2: Establish All Invariants in the Constructor

**Statement**: The constructor must validate all inputs and establish all class
invariants before returning the instance. No partially-constructed objects.

**Examples**:
- `Frac.__new__` normalizes sign, reduces by GCD, rejects zero denominator
- `Var.__new__` validates name against regex before caching
- `Amount.__new__` validates non-negativity

**Criterion**:
- Pass: every attribute is assigned before `return self`; validation precedes assignment
- Fail: attributes assigned conditionally or in separate setup methods

**Tooling**:
- Primary: `mypy --strict` (catches uninitialized attributes)
- LLM review for validation ordering

## PY-CC-3: Factory Pattern for Controlled Construction

**Statement**: When one class owns data required for constructing another (e.g.,
unique IDs), use the Factory pattern. The constructed class should refuse direct
instantiation.

**Pattern**: Constructor checks a guard flag set by the factory:
```python
if not factory._is_creating:
    raise TypeError("Use Factory.create() instead.")
```

**Criterion**:
- Pass: factory-created classes reject direct `ClassName()` calls
- Fail: classes requiring factory data allow direct construction

**Tooling**:
- Test: attempt direct construction in test, verify `TypeError` raised
- LLM review for factory relationship identification

## PY-CC-4: Context Manager as Construction Guard

**Statement**: When a factory needs to temporarily enable construction of another
class, use `@contextmanager` to manage the guard flag.

**Pattern**:
```python
@contextmanager
def _creating(self):
    self._is_creating = True
    yield
    self._is_creating = False
```

**Criterion**:
- Pass: guard flag is set/unset atomically via context manager
- Fail: bare boolean flag set without try/finally or context manager

**Tooling**:
- AST check: context manager wraps flag set/unset
- Grep: `grep -n "_is_creating"` to find guard flags and verify CM usage

## PY-CC-5: Alternative Constructors via @classmethod

**Statement**: Use `@classmethod` for alternative constructors that build
instances from different input types.

**Example**: `Frac.from_int(n)` creates a `Frac(n, 1)`.

**Criterion**:
- Pass: alternative constructors are classmethods, not standalone functions
- Fail: factory functions defined outside the class

**Tooling**:
- LLM review: methods named `from_*` should be `@classmethod`
- Grep: `grep -n "def from_"` and verify `@classmethod` decorator

## PY-CC-6: @dataclass for Pure Value Objects Only

**Statement**: Use `@dataclass(frozen=True, slots=True)` for simple immutable
value objects with no behavior beyond field storage. Always use both `frozen`
and `slots` flags.

**Criterion**:
- Pass: dataclasses are `frozen=True, slots=True`; no complex methods
- Fail: mutable dataclass, or dataclass used for class with significant behavior

**Tooling**:
- AST check: all `@dataclass` decorators include `frozen=True, slots=True`
- Grep: `grep -n "@dataclass"` and verify flags
