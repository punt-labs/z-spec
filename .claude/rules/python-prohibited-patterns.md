---
paths:
  - "**/*.py"
---

# Prohibited Patterns

These prohibitions supplement the ones stated in other rule files (PY-TS-9,
PY-TS-10, PY-TS-11, PY-EH-6, PY-EH-7).

## PL-PP-1: No Backwards-Compatibility Shims

**Statement**: When code changes, callers change. No `_old_name = new_name`
aliases, no `# removed` tombstones, no re-exports of dead symbols. If something
is removed, it is removed completely.

**Criterion**:

- Pass: renamed/removed symbols have no aliases or tombstone comments
- Fail: `old_function = new_function` for backwards compatibility

**Tooling**:

- LLM review: assignments that alias a renamed symbol
- Grep: `grep -rn "# removed\|# deprecated\|# backwards" src/`

## PL-PP-2: No Mock Objects in Production Code

**Statement**: Mock objects exist only in test code. Production code must never
import from `unittest.mock` or use mock-like patterns for runtime behavior.

**Criterion**:

- Pass: zero `unittest.mock` imports outside `tests/`
- Fail: `from unittest.mock import` in `src/`

**Tooling**:

- Grep: `grep -rn "unittest.mock\|from mock import" src/`

## PL-PP-3: No Defensive Coding at Non-Boundaries

**Statement**: Do not add try/except, null checks, or fallback logic in internal
code where invariants are established by the constructor or validated at the
boundary. Defensive coding hides bugs by silently handling conditions that
should never occur.

**Criterion**:

- Pass: internal methods trust invariants; only boundaries validate
- Fail: `if x is not None` deep in call chain where x is guaranteed by constructor

**Tooling**:

- LLM review: try/except blocks in non-boundary code
- Align with PY-EH-1 (validate at boundary) and PY-EH-5 (no defensive try/except)

## PL-PP-4: No Secrets in Code

**Statement**: API keys and credentials come from environment variables only.
No `.env` files committed, no hardcoded keys, no profiles.

**Criterion**:

- Pass: secrets from `os.environ` or `security` keychain; `.env` in `.gitignore`
- Fail: `API_KEY = "sk-..."` in source; `.env` tracked in git

**Tooling**:

- `punt pii` — scans for secrets
- Grep: `grep -rn "sk-\|api_key\s*=" --include="*.py" src/`
