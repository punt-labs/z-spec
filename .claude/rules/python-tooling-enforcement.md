---
paths:
  - "**/*.py"
---

# Tooling Enforcement Matrix

Every standard must be checkable. This file maps each rule to the tool(s) that
can deterministically judge compliance. Rules without deterministic tooling are
marked for LLM review — these are the gaps an agent must cover.

## Tier 1: Fully Automated (Tool Exits 0/1)

These tools exist, are mature, and produce deterministic pass/fail results.
An agent MUST run these before reporting compliance.

| Rule | Tool | Command | Pass |
|------|------|---------|------|
| PY-TS-2 | mypy | `uv run mypy src/ tests/` | exit 0 |
| PY-TS-4 | ruff | `ruff check --select UP035` | exit 0 |
| PY-TS-5 | ruff | `ruff check --select UP040` | exit 0 |
| PY-TS-8 | ruff | `ruff check --select UP007` | exit 0 |
| PY-CS-1 | ruff | `ruff check --select N` | exit 0 |
| PY-CS-2 | ruff | `ruff check --select I` | exit 0 |
| PY-CS-3 | ruff | `ruff format --check .` | exit 0 |
| PY-IC-2 | mypy | subclass of `@final` → error | exit 0 |
| PY-EH-3 | ruff | `ruff check --select S101` | exit 0 (config-dependent) |
| PY-OP-5 | ruff | `ruff check --select SIM,C1901` | exit 0 |

**Composite check command** (prefer `make check` over individual invocations):

```bash
make check
```

## Tier 0: OO Score (Custom, Deterministic, Exit Code 0/1)

The `tools/oo_score.py` script produces numeric OO quality metrics via AST
analysis. No external dependencies. Exits 1 if any metric fails.

| Metric | Threshold | What It Catches |
|--------|-----------|----------------|
| method_ratio | >= 0.80 | Procedural modules (functions not in classes) |
| encapsulation_ratio | == 1.0 | Public attributes (missing _ prefix) |
| avg_params | <= 4.0 | Parameter bloat (should be an object) |
| max_complexity | <= 10 | God functions (worst single function) |
| avg_complexity | <= 5.0 | Sustained complexity (many moderately-complex functions) |
| module_size | <= 300 | God modules |
| classes_per_module | <= 3 | Unfocused modules |
| class_to_func_ratio | >= 0.5 | Procedural code disguised as a module |
| init_violations | == 0 | **init** used instead of **new** |
| public_attr_violations | == 0 | self.name without underscore |
| future_annotations | == 1 | Missing from **future** import annotations |

**Usage**:

```bash
python tools/oo_score.py path/to/module.py           # human-readable
python tools/oo_score.py path/to/package/ --json      # machine-readable
python tools/oo_score.py path/to/package/ --threshold  # per-file breakdown
```

**Agent protocol**: Run before AND after every change. Score must not regress.

## Tier 0b: External OO Metrics (pip-installable, JSON output)

These complement `oo_score.py` with metrics it cannot compute.

**Install** (all work on Python 3.13):

```bash
uv tool install radon ruff cohesion vulture
```

### radon — Complexity and Maintainability

```bash
radon cc path/ -j               # cyclomatic complexity per function, JSON
radon mi path/ -j               # maintainability index per file, JSON
radon cc path/ -j -n C          # only show functions graded C or worse
```

Key thresholds:

- CC per function: A (1-5) good, B (6-10) moderate, C+ = flag for refactoring
- MI per file: >= 20 maintainable, < 10 unmaintainable

radon CC JSON includes `"type": "method"` vs `"type": "function"` — agent can
independently verify method_ratio.

### ruff PLR6301 — Methods That Don't Use self

```bash
ruff check --preview --select PLR6301 --output-format json path/
```

Detects methods that never access `self` — these are functions mis-placed inside
a class. Each finding is a sign of fake OO (procedural code in a class wrapper).

**Known false positives — do NOT "fix" these by removing self**:

- **Null Object pattern** (PY-DP-9): Methods that raise or return empty values
  without touching state. Example: `NullPort.buy()` raises `ValueError`.
  These must keep `self` to satisfy the parent interface.
- **`@singledispatchmethod` base**: The dispatch stub raises `TypeError` and
  never accesses `self`; the registered implementations do.
- **ABC/Protocol abstract methods**: A stub `raise NotImplementedError` body
  doesn't use `self` but the concrete implementations will.

**Agent rule**: When PLR6301 fires, check whether the method is in a Null Object
class, a singledispatch base, or an abstract method. These three patterns are
legitimate and must not be "fixed" by removing `self`. Handle them at the **repo
level**, not with a per-line `# noqa`: PLR6301 is preview-only, so either leave
it unselected in `[tool.ruff.lint]`, or scope it off interface files with
`[tool.ruff.lint.per-file-ignores]`. A per-line `# noqa: PLR6301` is counted by
the suppression ratchet (`make check-suppressions`) and fails the gate, so it is
not the sanctioned path even for these patterns. If no pattern applies, the
method genuinely doesn't belong on the class.

### pylint design category — Structural Smells

```bash
pylint --disable=all --enable=design --output-format=json2 path/
```

Key checks:

- R0903 too-few-public-methods (< 2 = data holder, not a real class)
- R0902 too-many-instance-attributes (> 7 = god class)
- R0913 too-many-arguments (> 5 = should be an object)
- R0901 too-many-ancestors (> 7 = deep hierarchy)

Exit code 8 when design violations found.

**Known false positives for R0903 (too-few-public-methods)**:

- **ABC/Protocol with 1 abstract method**: Strategy, Observer, Visitor, and
  callable interfaces legitimately define a single method. This is correct OO,
  not a data holder. Set `min-public-methods=1` in the repo's pylint config so
  this class never trips R0903 — do not add a per-class
  `# pylint: disable=too-few-public-methods`, which the suppression ratchet
  (`make check-suppressions`) counts and fails on.
- **How to tell a real R0903 from a false positive**:
  - Class inherits from `ABC` or `Protocol` with 1+ `@abstractmethod` →
    legitimate, covered by `min-public-methods=1`
  - Concrete class with 1 method + stored data → real smell, refactor
  - Class with 0 public methods (not a mixin) → always a real problem

### cohesion — LCOM (Class Cohesion)

```bash
cohesion -d path/ -b 50          # show classes with cohesion <= 50%
```

No JSON output. Measures what % of instance variables each method accesses.

- 0% = methods touch disjoint data (split the class)
- 30-70% = healthy range for real classes
- 100% = every method uses every variable (trivial class)

### Unified Gate Command: make check

All tools are unified in the project Makefile. Agents must use Make, not
individual tool invocations.

```bash
make check SRC=src/<package>/               # fail-fast gate (exits 0 or 1)
make report SRC=src/<package>/              # full diagnostics, no fail-fast
```

`make check` runs the full quality gate — lint, type checking, tests, and the
OO ratchet (`make check-oo`) — per PL-TC-5.
`make report` adds the diagnostics: radon CC/MI, pylint design, cohesion LCOM,
vulture dead code.

These rules define the required Makefile interface for Punt Labs Python
repos; a repo that has not yet adopted the ratchet acquires it per
`python-oo-adoption.md`.

See `make help` for all available targets.

## Tier 2: AST/Grep Checks (Scriptable, Deterministic)

These checks can be written as short Python scripts or shell one-liners.
An agent SHOULD run these or implement them as pre-commit hooks.

| Rule | Check | Command |
|------|-------|---------|
| PY-TS-1 | `from __future__ import annotations` present | `ruff check --select FA100` (exit 0) |
| PY-CC-1 | No `__init__` in non-dataclass classes | `grep -rn "def __init__" --include="*.py"` (zero hits) |
| PY-EN-1 | No public attributes | `grep -Pn "self\.[a-z][a-zA-Z_0-9]*\s*=" --include="*.py"` (zero hits) |
| PY-IC-4 | `__slots__` is a tuple | `grep -A1 "__slots__" --include="*.py"` → verify `(` not `[` |
| PY-CS-7 | `__all__` in `__init__.py` | `grep -L "__all__" */__init__.py` (zero hits) |
| PY-EH-2 | No bare `raise Exception` | `grep -n "raise Exception\b" --include="*.py"` (zero hits) |
| PY-OP-1 | Binary ops return `NotImplemented` | `grep -n "NotImplementedError" --include="*.py"` in operator methods (zero hits) |
| PY-OP-2 | `__eq__` paired with `__hash__` | AST: count per class, verify match |

PY-TS-1 needs only an existence check: placement is interpreter-enforced — a
`__future__` import anywhere but the top of the file is a `SyntaxError`.

**Composite grep check**:

```bash
grep -rn "def __init__" --include="*.py" src/
grep -Pn "self\.[a-z][a-zA-Z_0-9]*\s*=" --include="*.py" src/
grep -rn "raise Exception\b" --include="*.py" src/
grep -rn "NotImplementedError" --include="*.py" src/
```

- The `self.` assignment and `raise Exception` greps must return zero results.
- `def __init__` hits require manual audit for the `@dataclass` exception
  (PY-CC-1): the decorator sits on the class line, not the `def __init__`
  line, so no line filter can express it. The Tier 3 `check_no_init()` AST
  check automates the exception.
- `NotImplementedError` hits are legitimate only in abstract method stubs,
  never in binary operator methods, per PY-OP-1.

## Tier 3: Custom AST Analysis Script

For rules needing deeper analysis, write a Python script using `ast` module.
Each check is a function returning pass/fail with file:line details.

**Checks to implement in a custom AST script** (e.g., `tools/check_standards.py`):

```text
check_future_annotations()    # PY-TS-1: first import is __future__
check_no_init()               # PY-CC-1: no __init__ (exclude dataclasses)
check_no_public_attrs()       # PY-EN-1: all self.X assignments use _prefix
check_slots_are_tuples()      # PY-IC-4: __slots__ assigned a tuple
check_operators_return_NI()   # PY-OP-1: binary ops have NotImplemented branch
check_eq_hash_pairing()       # PY-OP-2: __eq__ and __hash__ co-occur
check_init_py_has_all()       # PY-CS-7: __init__.py has __all__
check_no_bare_exception()     # PY-EH-2: raise uses specific exception types
check_operators_no_mutation()  # PY-OP-7: operators don't assign to self
check_mutators_return_none()  # PY-OP-8: mutating methods return None
```

## Tier 2b: Heuristic Checks (Scriptable, Threshold-Based)

These checks produce warnings, not hard failures. They flag code smell.

| Rule | Check | Command |
|------|-------|---------|
| PY-OO-1 | Function:class ratio | `grep -c "^def " mod.py` vs `grep -c "^class " mod.py` — flag ratio > 5:1 |
| PY-OO-2 | Module size | `wc -l mod.py` — flag if > 300 |
| PY-OO-2 | Classes per module | AST: count `ClassDef` nodes — flag if > 3 |
| PY-OO-3 | Parameter count | `ruff check --select PLR0913` (set max-args=4) |

## Tier 4: LLM Review Required

These rules require semantic understanding and cannot be checked by tools alone.
An agent must reason about the code to check these.

| Rule | What to Check |
|------|--------------|
| PY-OO-1 | Domain nouns with data + behavior are classes, not dicts + functions |
| PY-OO-4 | TypedDicts not used as substitute for domain classes with behavior |
| PY-OO-5 | Functions that read 3+ fields from an arg should be methods |
| PY-OO-6 | Pattern triggers recognized and applied (see trigger table) |
| PY-TS-6 | Protocol vs ABC selection matches interface/implementation distinction |
| PY-CC-2 | All invariants established before `return self` |
| PY-CC-3 | Factory-created classes reject direct construction |
| PY-EN-3 | Private vs protected choice matches subclass-safety need |
| PY-EN-4 | All write paths for validated attributes run validation |
| PY-EN-5 | Stale attributes deleted after state transitions |
| PY-IC-1 | Liskov Substitution: subclass behavior is substitutable |
| PY-IC-3 | Mixins have no constructor and no instance data |
| PY-IC-5 | Explicit dispatch only used for diamond resolution |
| PY-IC-6 | Single Responsibility: each component has one job |
| PY-IC-7 | Open-Closed: new subclass doesn't modify parent |
| PY-OP-3 | Coercion pattern used (not duplicated logic per type) |
| PY-OP-4 | **str** is human-readable, **repr** is developer-readable |
| PY-OP-6 | Properties are lightweight, methods are computational |
| PY-DP-1..9 | Correct pattern selected for the problem at hand |
| PY-EH-1 | Validation at boundary, trust internally |
| PY-EH-4 | Boolean returns for non-exceptional failures |
| PY-EH-5 | No defensive try/except in internal code |

## Agent Enforcement Protocol

When an agent writes or reviews Python code in this project:

1. **Pre-write**: Load applicable rules from `.claude/rules/` based on file path.
2. **Post-write**: Run Tier 1 commands. Fix any failures before reporting done.
3. **Post-write**: Run Tier 2 grep checks. Fix any failures.
4. **Review**: Apply Tier 4 checklist to changed code. Flag violations.
5. **Report**: List which rules were checked and their pass/fail status.
