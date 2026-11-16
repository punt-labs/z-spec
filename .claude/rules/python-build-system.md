---
paths:
  - "**/*.py"
  - "Makefile"
---

# Build System Standards

## PY-BS-1: All Checks Must Be in the Makefile

**Statement**: Every quality check tool must have a corresponding Make target.
No check should exist only as a shell command in documentation — it must be
runnable via `make <target>`.

**Required targets**:

- `make check` — runs all checks, fail-fast (exits non-zero on first failure)
- `make report` — runs all checks and reports, continues past failures
- Individual targets for each tool (see below)

**Criterion**:

- Pass: `make check` runs and covers OO score, types, formatting, lint,
  complexity, and design checks
- Fail: any check exists only in documentation or CLAUDE.md but not in Makefile

**Tooling**:

- `make -n check` — dry-run to verify all targets resolve
- `grep -c "^check-" Makefile` — count individual check targets

## PY-BS-2: make check Is the Single Gate

**Statement**: An agent must run `make check` (or `make check SRC=<module>`)
before reporting any code change as done. This replaces all ad-hoc tool
invocations. If `make check` exits 0, the code passes. If it exits non-zero,
the code fails.

**Criterion**:

- Pass: agent runs `make check` and it exits 0
- Fail: agent runs individual tools instead of `make check`, or skips checks

**Tooling**:

- `make check SRC=path/to/module/` — scoped to changed module
- `make report SRC=path/to/module/` — full report including non-fatal checks

## PY-BS-3: make report for Full Visibility

**Statement**: `make report` runs every check AND every diagnostic tool (cohesion,
dead code, maintainability index) without stopping on failure. Use this for
baseline measurement before refactoring and for end-of-session summaries.

**Required report sections** (each prints a labeled header):

1. OO Score (tools/oo_score.py --threshold)
2. Type Safety (mypy --strict)
3. Formatting (ruff format --check)
4. Lint (ruff with OO-relevant rules)
5. Complexity (radon CC, grade C+ flagged)
6. Maintainability Index (radon MI)
7. Design Smells (pylint design category)
8. Class Cohesion (cohesion LCOM)
9. Dead Code (vulture)

**Criterion**:

- Pass: `make report` produces all 9 sections with labeled output
- Fail: any section missing or tool not installed

**Tooling**:

- `make report SRC=path/` — run and read output

## PY-BS-4: Makefile Must Be Portable

**Statement**: The Makefile must work across projects without modification.
Tool invocations run through `uv run` (PL-TC-1), so no interpreter or
virtualenv path is ever hardcoded, and the source path is overridable via
`SRC` so checks can be scoped to one package.

**Usage examples**:

```bash
make check SRC=src/<package>/           # scope to one package
make report SRC=src/<package>/          # scoped diagnostics
```

**Criterion**:

- Pass: `make check SRC=...` works without editing the Makefile; tools run via `uv run`
- Fail: tool, interpreter, or virtualenv paths are hardcoded

**Tooling**:

- `grep -c "?=" Makefile` — verify variables use conditional assignment

## PY-BS-5: Enforcement Tools Must Pass Their Own Checks

**Statement**: Any custom tool that enforces coding standards (e.g.,
`tools/oo_score.py`) must itself pass `make check`. A tool that fails its own
rules has no authority to enforce them on other code.

**Criterion**:

- Pass: `python tools/oo_score.py tools/` exits 0
- Fail: enforcement tool has OO score violations

**Tooling**:

- `make check SRC=tools/` — must pass before committing tool changes

## PY-BS-6: Every Module Must Have Tests

**Statement**: Untested code is unfinished code. Every source module must have a
corresponding test file. Tests mirror source structure.

**Naming**: `src/package/core.py` → `tests/test_core.py`.

**Criterion**:

- Pass: every `.py` module in `src/` has a corresponding `test_*.py` in `tests/`
- Fail: source module with no test file

**Tooling**:

- Shell check: for each `src/**/*.py`, verify `tests/test_*.py` exists
- `make test` target must exist and run the test suite
- pytest: `pytest --co -q` lists collected tests (zero = fail)
