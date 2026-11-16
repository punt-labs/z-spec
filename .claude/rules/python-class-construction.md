---
paths:
  - "**/*.py"
---

# Class Construction Standards

## PY-CC-1: Use __new__ as the Constructor

__Statement__: Use `__new__` instead of `__init__` for class construction.
`__new__` controls instance creation; `__init__` merely initializes an
already-created instance.

__Rationale__: `__new__` is required for flyweight/singleton patterns (controlling
whether a new object is created), for `@final` classes, and for consistency with
the metaclass `type.__call__` dispatch. Using it uniformly means construction
control is always available without rewriting the constructor later.

__Pattern__:

```python
def __new__(cls, ...) -> Self:
    self = super().__new__(cls)
    self._field = value
    return self
```

__Criterion__:

- Pass: classes use `__new__` with `super().__new__(cls)`, return `self`
- Fail: class defines `__init__` (exception: `@dataclass` which generates it)

__Tooling__:

- AST check: `grep -rn "def __init__" --include="*.py"` should return zero hits
  (excluding dataclasses and third-party code)
- Custom ruff rule or pylint checker for `__init__` presence

## PY-CC-2: Establish All Invariants in the Constructor

__Statement__: The constructor must validate all inputs and establish all class
invariants before returning the instance. No partially-constructed objects.

__Examples__:

- A `Fraction.__new__` normalizes sign, reduces by GCD, rejects a zero denominator
- An identifier type's `__new__` validates the name against a regex before caching
- An `Amount.__new__` validates non-negativity

__Criterion__:

- Pass: every attribute is assigned before `return self`; validation precedes assignment
- Fail: attributes assigned conditionally or in separate setup methods

__Tooling__:

- Primary: `mypy --strict` (catches uninitialized attributes)
- LLM review for validation ordering

## PY-CC-3: Factory Pattern for Controlled Construction

__Statement__: When one class owns data required for constructing another (e.g.,
unique IDs), use the Factory pattern. The constructed class should refuse direct
instantiation.

__Pattern__: Constructor checks a guard flag set by the factory:

```python
if not factory._is_creating:
    raise TypeError("Use Factory.create() instead.")
```

__Criterion__:

- Pass: factory-created classes reject direct `ClassName()` calls
- Fail: classes requiring factory data allow direct construction

__Tooling__:

- Test: attempt direct construction in test, verify `TypeError` raised
- LLM review for factory relationship identification

## PY-CC-4: Context Manager as Construction Guard

__Statement__: When a factory needs to temporarily enable construction of another
class, use `@contextmanager` to manage the guard flag.

__Pattern__:

```python
@contextmanager
def _creating(self):
    self._is_creating = True
    yield
    self._is_creating = False
```

__Criterion__:

- Pass: guard flag is set/unset atomically via context manager
- Fail: bare boolean flag set without try/finally or context manager

__Tooling__:

- AST check: context manager wraps flag set/unset
- Grep: `grep -n "_is_creating"` to find guard flags and verify CM usage

## PY-CC-5: Alternative Constructors via @classmethod

__Statement__: Use `@classmethod` for alternative constructors that build
instances from different input types.

__Example__: `Fraction.from_int(n)` creates a `Fraction(n, 1)`.

__Criterion__:

- Pass: alternative constructors are classmethods, not standalone functions
- Fail: factory functions defined outside the class

__Tooling__:

- LLM review: methods named `from_*` should be `@classmethod`
- Grep: `grep -n "def from_"` and verify `@classmethod` decorator

## PY-CC-6: @dataclass for Pure Value Objects Only

__Statement__: Use `@dataclass(frozen=True, slots=True)` for simple immutable
value objects with no behavior beyond field storage. Always use both `frozen`
and `slots` flags.

__Criterion__:

- Pass: dataclasses are `frozen=True, slots=True`; no complex methods
- Fail: mutable dataclass, or dataclass used for class with significant behavior

__Tooling__:

- AST check: all `@dataclass` decorators include `frozen=True, slots=True`
- Grep: `grep -n "@dataclass"` and verify flags
