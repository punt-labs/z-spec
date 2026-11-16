---
paths:
  - "**/*.py"
---

# Operator and Dunder Protocol Standards

## PY-OP-1: Return NotImplemented from Binary Operators

**Statement**: Binary operator methods (`__add__`, `__mul__`, `__eq__`, etc.)
must return the `NotImplemented` sentinel (not raise `NotImplementedError`)
when the other operand is an unrecognized type.

**Rationale**: `NotImplemented` tells the runtime to try the reflected operation
on the other operand. Raising an exception prevents this fallback.

**Criterion**:

- Pass: `return NotImplemented` for unrecognized types
- Fail: `raise NotImplementedError` or `return False` from `__eq__`

**Tooling**:

- AST check: binary operator methods contain `return NotImplemented` branch
- Grep: `grep -n "NotImplementedError" --include="*.py"` in operator methods
- ruff: `E711` (comparison to None) tangentially related

## PY-OP-2: **eq** and **hash** Contract

**Statement**: If you override `__eq__`, you must also override `__hash__`.
`x == y` must imply `hash(x) == hash(y)`. Include the class in the hash tuple
to reduce cross-type collisions.

**Pattern**: `return hash((ClassName, self._field1, self._field2))`

**Criterion**:

- Pass: class with custom `__eq__` also defines `__hash__`; hash includes class
- Fail: custom `__eq__` without `__hash__` (Python sets `__hash__ = None`)

**Tooling**:

- mypy: warns about `__eq__` without `__hash__` in some configurations
- AST check: class with `__eq__` must also have `__hash__`
- Grep: `grep -c "__eq__"` vs `grep -c "__hash__"` per class

## PY-OP-3: Coercion Pattern for Mixed-Type Operators

**Statement**: For operators accepting mixed types (e.g., `Fraction + int`),
coerce the foreign type to the class type first, then fall through to the
homogeneous logic. Do not duplicate logic for each type combination.

**Pattern**:

```python
def __add__(self, other: object) -> Fraction:
    if isinstance(other, int):
        other = Fraction.from_int(other)
    if not isinstance(other, Fraction):
        return NotImplemented
    # single homogeneous implementation follows
```

**Criterion**:

- Pass: one implementation path after coercion
- Fail: separate branches for each type combination

**Tooling**:

- LLM review: check operator methods for duplicated logic across types

## PY-OP-4: **str** for Humans, **repr** for Developers

**Statement**: `__str__` returns human-readable output. `__repr__` returns
developer/debug output matching constructor call syntax (`ClassName(args)`).

**Criterion**:

- Pass: `__repr__` returns `f"ClassName({fields})"` format; `__str__` is clean
- Fail: only one of str/repr defined; repr returns human-friendly string

**Tooling**:

- AST check: classes with `__str__` should also have `__repr__` (and vice versa)
- Test: `repr(obj)` produces a string starting with the class name

## PY-OP-5: **bool** and **len** Interaction

**Statement**: Implementing `__len__` automatically provides `__bool__` (truthy
when non-empty). If you implement `__len__`, you get `__bool__` for free and
can use `if collection:` instead of `if len(collection) > 0:`.

**Criterion**:

- Pass: container classes implement `__len__`; code uses `if container:`
- Fail: explicit `len() > 0` checks on objects with `__len__`

**Tooling**:

- ruff: `SIM103` / `C1901` (truthiness checks)
- Grep: `grep -Pn "len\(\w+\)\s*[>!=]"` to find verbose truthiness checks

## PY-OP-6: Properties Behave Like Attributes, Methods Require Calls

**Statement**: Use `@property` for attribute-like access (no computation or
lightweight computation). Use methods for operations that involve computation.
Never confuse the caller about which is which.

**Criterion**:

- Pass: `obj.name` for properties; `obj.compute()` for methods
- Fail: property that performs expensive computation; method returning stored data

**Tooling**:

- LLM review: audit properties for computational complexity
- Heuristic: property body > 3 lines → consider making it a method

## PY-OP-7: Immutable Objects Return New Instances from Operators

**Statement**: When a class is immutable, all operator methods must return new
instances (or cached flyweight instances). No operator may mutate `self`.

**Criterion**:

- Pass: `__add__` returns `ClassName(...)`, not `self` (except `__pos__`)
- Fail: operator modifies `self._field` and returns `self`

**Tooling**:

- AST check: operator methods must not contain `self._field =` assignments
- LLM review: verify immutability contract

## PY-OP-8: Mutating Methods Return None

**Statement**: Methods that modify the object in place must return `None`.
Only operators and fluent-API methods (Builder pattern) return `self`.

**Criterion**:

- Pass: `add()`, `remove()`, `update()` return `None`
- Fail: mutating method returns `self` without Builder justification

**Tooling**:

- mypy: return type annotation `-> None` on mutating methods
- AST check: methods with `self._field =` should return `None` (unless Builder)
