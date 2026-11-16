---
paths:
  - "**/*.py"
---

# Error Handling Standards

## PY-EH-1: Validate at the Boundary, Trust Internally

**Statement**: Validate inputs at construction time and at public API boundaries.
Internal methods may assume invariants established by the constructor and
validated setters.

**Example**: an `Amount.__new__` validates non-negativity. An `Order` dataclass
holding an `Amount` trusts it — the value is guaranteed valid by its own
constructor, so `Order` does not re-validate it.

**Criterion**:

- Pass: public constructors and setters validate; private methods trust invariants
- Fail: redundant validation deep in call chains; or missing validation at entry

**Tooling**:

- LLM review: audit public API entry points for validation
- Test: pass invalid inputs to constructors, verify errors

## PY-EH-2: Error Type Selection

| Situation | Error Type |
|-----------|-----------|
| Invalid argument value | `ValueError` |
| Wrong type (construction bypass) | `TypeError` |
| Division by zero | `ZeroDivisionError` |
| State violation (wrong state) | `ValueError` |
| Iterator exhausted | `StopIteration` |
| Key not found (expected) | `KeyError` (let propagate) |

**Criterion**:

- Pass: error type matches the table above
- Fail: generic `Exception` or `RuntimeError` for specific situations

**Tooling**:

- AST check: `raise` statements use specific exception types, never bare `Exception`
- Grep: `grep -n "raise Exception\b"` should return zero hits

## PY-EH-3: Never Use assert for User-Facing Validation

**Statement**: `assert` is for developer invariant checks only. It is removed
when running with `-O`. Use explicit `if/raise` for all validation that should
survive optimization.

**Criterion**:

- Pass: `assert` only in internal consistency checks; public validation uses `if/raise`
- Fail: `assert isinstance(x, int)` in public API; `assert state == "draft"` in
  public method

**Tooling**:

- AST check: `assert` not in public methods (methods without leading `_`)
- ruff: `S101` (use of assert detected) — configure to allow in private methods
- Grep: `grep -n "assert " --include="*.py"` and verify each is internal-only

## PY-EH-4: Boolean Returns for Non-Exceptional Failures

**Statement**: When a failure is normal (not exceptional), return `False` instead
of raising an exception. Reserve exceptions for genuine error conditions.

**Examples**:

- A deduplicating stack's `push()` returns `False` if the item is already present
- A ranked stack's `place()` returns `False` if the new entry doesn't beat the top
- A container's `remove()` returns `False` if the item is not found

**Criterion**:

- Pass: expected "no-op" scenarios return `False`; unexpected states raise
- Fail: exception for a predictable, non-erroneous condition

**Tooling**:

- LLM review: methods that can "fail normally" should return bool, not raise
- mypy: return type annotation includes `bool` for failable operations

## PY-EH-5: No Defensive try/except in Internal Code

**Statement**: Do not use try/except for flow control within a class. Structure
code so that invariants prevent errors rather than catching them.

**Criterion**:

- Pass: no try/except in internal methods; errors prevented by validation
- Fail: try/except wrapping internal calls that should never fail

**Tooling**:

- Grep: `grep -c "try:" --include="*.py"` — minimize occurrences
- LLM review: each try/except must have justification (e.g., external I/O)

## PY-EH-6: Never Catch Broad Exception

**Statement**: Never `except Exception` unless re-raising or at a system boundary
(CLI entry point, MCP tool handler, top-level event loop). Catching broad
exceptions masks bugs and violates fail-fast.

**Criterion**:

- Pass: every `except Exception` either re-raises or is at the outermost boundary
- Fail: `except Exception: pass` or `except Exception as e: log(e)` in library code

**Tooling**:

- ruff: `BLE001` (blind-except) catches bare `except:` and `except Exception:`
- `ruff check --select BLE001`
- Grep: `grep -n "except Exception" --include="*.py"` — audit each hit

## PY-EH-7: No Warning Filters

**Statement**: Do not use `warnings.filterwarnings("ignore")` or
`@pytest.mark.filterwarnings` to suppress warnings. Fix the root cause.

**Criterion**:

- Pass: zero warning suppression in source or test code
- Fail: `warnings.filterwarnings("ignore")` or `simplefilter("ignore")`

**Tooling**:

- Grep: `grep -rn "filterwarnings\|simplefilter" --include="*.py"` — zero hits

## PY-EH-8: Raise, Don't Return None, on Unrepresentable Values

**Statement**: When a function's contract is to *return a typed value*
and the input makes producing that value impossible, **raise an
exception**. Do not return `None`, an empty container, a magic sentinel,
or a default. The return type is a promise — fulfil it or fail loud.

**Rationale**: Every `-> T | None` is a place the type system gave up.
The caller has to remember to check, the check rots, and when the check
is missing the wrong-default-value gets silently used instead of failing
loud. The bug surfaces somewhere far from its cause and the wrong-value
case may never be observed in testing.

**The PY-EH-4 distinction**: PY-EH-4 allows `bool` returns for operations
whose success/failure is normal and the caller's next action depends on
which happened (`push()` returning `False` when the item is already
present; the caller may keep trying). PY-EH-8 forbids `-> T | None` for *value-producing*
functions whose job is to yield a `T`. A parser that can't parse, a
lookup that can't find, a conversion that can't convert — these raise.

**Decision table**:

| Function's job | Bad input behavior |
|----------------|-------------------|
| Parse `str` → `int` | Raise `ValueError` (NOT return `None`) |
| Coerce wire value → typed value | Raise `ValueError` (NOT return `None`) |
| Look up required record by ID | Raise `KeyError` or `LookupError` (NOT return `None`) |
| Look up *optional* record by ID | Return `None` is fine — absence is the documented contract |
| Try-write an item to a deduplicating set | Return `bool` — both outcomes are normal (PY-EH-4) |
| Validate constructor argument | Raise `ValueError` (NOT silently coerce or accept) |

**Examples — bad**:

```python
def coerce_number(raw: object) -> float | None:
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        return None
    return float(raw)


def object_sequence(raw: object) -> tuple[object, ...] | None:
    if not isinstance(raw, list | tuple):
        return None
    return tuple(raw)


# Every caller is forced into the same pattern:
n = coerce_number(raw)
if n is None:
    raise ValueError(...)
```

**Examples — good**:

```python
def require_number(self, raw: object, field: str) -> float:
    """Return ``raw`` as a ``float`` or raise."""
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise self.field_error(field, "a number", raw)
    return float(raw)


def require_sequence(self, raw: object, field: str) -> tuple[object, ...]:
    if not isinstance(raw, list | tuple):
        raise self.field_error(field, "a list or tuple", raw)
    return tuple(raw)
```

The signature changed from `T | None` to `T`. Every caller stops
checking. The function decides; the caller trusts.

**When `Optional` IS appropriate**:

- The *absence* of a value is part of the function's contract, not a
  failure mode. `dict.get(key, default=None)` returns `None` when the
  key is absent because absence is the API. Looking up an *optional*
  user setting is the same.
- The function is part of a Maybe-style chain where `None` is the
  short-circuit value AND every caller actively handles it (this is
  rare in practice; usually a real `Result` type is better).
- The field is a discriminated *state* of an entity that genuinely has
  "no value" semantics (e.g., `User.spouse: User | None` for unmarried
  users). The Optional is data, not error signalling.

Everything else: raise.

**Criterion**:

- Pass: zero `-> T | None` return types on parser/converter/lookup
  functions whose contract is "produce a `T`".
- Fail: any `def foo(...) -> T | None` where `None` means "could not
  produce a `T`".

**Tooling**:

- Grep: `grep -rn "-> .* | None\|-> Optional\[" --include="*.py" src/`
  — audit each hit. For each, ask: is `None` the documented contract
  for absence (good), or is it "I gave up trying to produce a value"
  (bad)?
- LLM review: a function returning `T | None` whose body has `return
  None` inside a validation branch is almost always a violation. The
  fix: `raise ValueError(...)` and change the signature to `-> T`.
