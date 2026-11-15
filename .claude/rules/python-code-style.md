---
paths:
  - "**/*.py"
---

# Code Style Standards

## PY-CS-1: Naming Conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| Class | PascalCase | `BidStack`, `WithdrawableStack` |
| Method/Function | snake_case | `draft_listing`, `count_money` |
| Protected attribute | `_name` | `_num`, `_den`, `_username` |
| Private attribute | `__name` | `__items`, `__state`, `__bids` |
| Type alias | PascalCase | `Scalar`, `ListingState` |
| Constants / Compiled regex | UPPER_SNAKE | `VARNAME_PATTERN` |
| TypeVar (legacy) | Single uppercase | `T`, `S`, `ItemT` |

**Tooling**:
- Primary: `ruff check --select N` (pep8-naming)
- Supplemental: `pylint --enable=C0103`

## PY-CS-2: Import Organization

**Order** (each group separated by blank line):
1. `from __future__ import annotations`
2. Standard library (`abc`, `collections.abc`, `math`, `re`, `typing`, `weakref`)
3. Third-party packages
4. Local/relative imports

**Style**: Prefer `from X import Y` over bare `import X` (exception: `import re`
is acceptable for small modules).

**Tooling**:
- Primary: `ruff check --select I` (isort rules)
- Alternative: `isort --check-only --diff`

## PY-CS-3: Formatting

**Statement**: Use ruff for formatting. Default line length 88 characters.

**Tooling**:
- Primary: `ruff format --check .`

## PY-CS-4: __slots__ for Memory-Critical Classes

**Statement**: Use `__slots__` on classes that will have many instances, to avoid
the 296-byte `__dict__` overhead per instance. Always declare as tuple.

**When to use**: Data-heavy value objects, vector types, nodes in large trees.
**When to skip**: Classes with dynamic attributes or small instance counts.

**Criterion**:
- Pass: `__slots__` defined as tuple; no `__dict__` access attempted
- Fail: `__slots__` defined as list or dict

**Tooling**:
- AST check: `__slots__` RHS is `ast.Tuple`
- `sys.getsizeof()` comparison in tests for critical paths

## PY-CS-5: f-string Debug Format

**Statement**: Use f-string `=` specifier for debug output: `f"{expr = }"`.
Use `!s` for str representation, `!r` for repr.

**Tooling**:
- LLM review: print statements in tests use `=` specifier

## PY-CS-6: Module Structure

**Statement**: One concept per module file. Module-level docstring required.
Classes, then module-level code. No executable code at module level in
library modules (only in test/demo scripts).

**Tooling**:
- Grep: `grep -L '"""' *.py` to find modules missing docstrings
- AST check: module body starts with `ast.Expr(value=ast.Constant(kind=str))`

## PY-CS-7: __all__ in Package __init__.py

**Statement**: Every `__init__.py` must define `__all__` listing explicitly
re-exported names. Use relative imports.

**Criterion**:
- Pass: `__all__ = ["Marketplace"]` present; relative imports used
- Fail: no `__all__`; absolute imports within the package

**Tooling**:
- Grep: `grep -L "__all__" */__init__.py`
- mypy: reports "not explicitly exported" warnings when `__all__` is missing

## PY-CS-8: TypedDict for Structured Dictionaries

**Statement**: Use `TypedDict` (not plain `dict`) when a dictionary has known
string keys with specific value types. Use `total=False` when keys are optional
by default; annotate individual keys with `Required`/`NotRequired` as needed.

**Tooling**:
- mypy: enforces TypedDict key/value types
- LLM review: plain `dict[str, Any]` that could be a TypedDict → flag

## PY-CS-9: Double Quotes and Line Length

**Statement**: Use double quotes for strings. Line length 88 characters. Both
enforced by ruff configuration.

**Tooling**:
- Primary: `ruff format --check .`

## PY-CS-10: All Imports at Top of File

**Statement**: All imports must be at the top of the file, grouped per PEP 8
(stdlib, third-party, local). No inline imports inside functions or methods.

**Exception**: `if TYPE_CHECKING:` guard imports (PY-TS-7) and lazy imports for
optional heavy dependencies at system boundaries.

**Criterion**:
- Pass: all `import` and `from ... import` statements in the header block
- Fail: `import X` inside a function body (unless guarded lazy import)

**Tooling**:
- ruff: `E402` (module-level-import-not-at-top-of-file)
- `ruff check --select E402`

## PY-CS-11: Logging Convention

**Statement**: Every module that logs must use
`logger = logging.getLogger(__name__)`. Configure `logging.basicConfig()` once
in the entry point (CLI main, server main), never in library modules.

**Criterion**:
- Pass: `getLogger(__name__)` used; no `basicConfig()` in library code
- Fail: `print()` used for operational output; `basicConfig()` in a library module

**Tooling**:
- Grep: `grep -rn "basicConfig" --include="*.py" src/` — only in entry points
- Grep: `grep -rn "print(" --include="*.py" src/` — flag in non-test code

## PY-CS-12: Walrus Operator for Inline Assignment

**Statement**: Use `:=` (walrus operator) when an assignment-as-expression
reduces repetition or clarifies flow. Common in cache checks and conditional
assignments.

**Examples**:
- `if item not in (items := self.__items):` — assign + use in one line
- `stack.push(new_bid := Bid(buyer, amount))` — create + push

**Tooling**:
- LLM review: patterns where a variable is assigned then immediately used once
  could use walrus operator
