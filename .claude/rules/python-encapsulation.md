---
paths:
  - "**/*.py"
---

# Encapsulation Standards

## PY-EN-1: No Public Data Attributes

**Statement**: Never expose raw data attributes publicly. All instance attributes
must be prefixed with `_` (protected) or `__` (private/name-mangled).

**Rationale**: A public attribute is publicly settable and gettable — any caller
can mutate it, bypassing every invariant the class maintains. Never make
attributes public. Instead: use properties for read-only access, and property
setters for managed write access (with validation).

**Criterion**:

- Pass: all instance attributes start with `_` or `__`
- Fail: any `self.name = value` where `name` has no leading underscore

**Tooling**:

- AST check: walk all `ast.Attribute` nodes in `__new__`; verify `attr` starts with `_`
- Custom ruff plugin or pylint checker
- Regex: `grep -Pn "self\.[a-z][a-zA-Z_]*\s*=" --include="*.py"` (finds `self.foo =`)

## PY-EN-2: Properties for Read-Only Access

**Statement**: Expose internal state via `@property` with no setter. This is the
default access pattern.

**Pattern**:

```python
_name: str


@property
def name(self) -> str:
    return self._name
```

**Criterion**:

- Pass: every externally-readable attribute has a `@property` getter
- Fail: callers access `obj._name` directly from outside the class

**Tooling**:

- Primary: `mypy --strict` with pyright (catches some access violations)
- Grep: `grep -Pn "\b\w+\._[a-z]"` in test/client code (accessing protected attrs)
- LLM review for property completeness

## PY-EN-3: Private (Double Underscore) for Subclass-Unsafe Attributes

**Statement**: Use `__name` (name mangling) when subclass collision would break
invariants. Use `_name` (protected) when subclass access is acceptable.

**When to use `__`**:

- Internal data that subclasses must not overwrite (e.g., `__items`, `__state`)
- Cache attributes (e.g., `__hash_cache`)

**When to use `_`**:

- Attributes that subclasses may reasonably read (e.g., `_num`, `_den` in a
  fraction type)
- Protected methods called by subclasses
- Guard flags read by a collaborating class (e.g., the factory's
  `_is_creating` checked in PY-CC-3 — name mangling would break the
  cross-class check)

**Criterion**:

- Pass: double underscore used for truly internal state; single underscore for
  protected state accessible to subclasses
- Fail: all attributes use `_` in a class hierarchy where subclass collision is possible

**Tooling**:

- LLM review (requires understanding class hierarchy intent)
- Heuristic: leaf/`@final` classes can use `_`; non-final classes with subclasses
  should prefer `__` for internal state

## PY-EN-4: Validated Attribute Access via Descriptors or Property Setters

**Statement**: When an attribute requires validation on write, use either a
`@property` setter or a descriptor. Validated public attributes via descriptors
do not violate encapsulation.

**Pattern (descriptor)**:

```python
class ValidatedAttr[T]:
    def __set__(self, instance, value: T) -> None:
        self._validator(value)
        instance.__dict__[self._name] = value
```

**Criterion**:

- Pass: writable attributes validated on every write
- Fail: raw attribute assignment without validation in any setter path

**Tooling**:

- LLM review: audit all assignment paths for validated attributes
- Test: attempt invalid assignment, verify error raised

## PY-EN-5: Delete Stale State After Transitions

**Statement**: When an object transitions state, delete attributes that are no
longer valid. This prevents stale access.

**Example**: after an order transitions to its completed state, delete the
`__pending_items` and `__start_time` attributes that only the active state owns.

**Criterion**:

- Pass: `del self.__attr` for attributes invalid in the new state
- Fail: stale attributes remain accessible after transition

**Tooling**:

- LLM review: audit state transition methods for cleanup
- Test: attempt to access old-state attributes after transition, verify error
