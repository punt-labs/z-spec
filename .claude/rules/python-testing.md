---
paths:
  - "**/*.py"
  - "tests/**"
---

# Testing Standards

## PL-TT-1: Four-Tier Testing Pyramid

**Statement**: Every project must define and maintain a testing pyramid with
four tiers. Default `pytest` runs tiers 1-2. Higher tiers are opt-in.

| Tier | What It Tests | Speed | Runs in CI |
|------|---------------|-------|------------|
| 1. Unit | Tool logic, data models, pure functions | ~1s | Yes |
| 2. Integration | MCP protocol, cross-component state | ~2-5s | Yes |
| 3. Subprocess/E2E | Wire protocol, CLI args, process lifecycle | ~5-10s | Optional |
| 4. SDK | End-to-end with Claude (costs money) | ~30s | No |

**Criterion**:
- Pass: tiers 1-2 run in `make test`; tiers 3-4 behind pytest markers
- Fail: no tier separation; all tests are slow; or no tests at all

**Tooling**:
- `uv run pytest` — tiers 1-2
- `uv run pytest -m integration` — tier 2 only
- `uv run pytest -m e2e` — tier 3
- Markers: `@pytest.mark.integration`, `@pytest.mark.e2e`, `@pytest.mark.sdk`

## PL-TT-2: Coverage Increases With Every Change

**Statement**: When you touch a file, its test coverage must not decrease. When
you add a function, it gets tests. When you fix a bug, the fix includes a
regression test.

**Criterion**:
- Pass: new code has corresponding tests; bug fixes include reproduction test
- Fail: new function without test; bug fix without regression test

**Tooling**:
- LLM review: diff includes test changes proportional to source changes
- `uv run pytest --co -q` before and after — test count should not decrease

## PL-TT-3: Tests Document Behavior

**Statement**: The test suite is the executable specification. When someone asks
"what happens when X?", the answer should be in a test. Tests that only verify
happy paths are incomplete.

**Criterion**:
- Pass: error paths, edge cases, and boundary conditions are tested
- Fail: only happy-path tests; error handling untested

**Tooling**:
- LLM review: for each public function, are error cases tested?

## PL-TT-4: Test Infrastructure Is First-Class

**Statement**: Fixtures, factories, helpers, and test utilities are real code
that deserves the same quality as production code. Flaky tests are bugs. Slow
tests are performance issues.

**Criterion**:
- Pass: shared fixtures in conftest.py; no copy-paste between test files
- Fail: duplicated setup code across tests; flaky tests ignored

**Tooling**:
- Grep: duplicate setup patterns across test files
- CI: flaky test = immediate fix, not retry

## PL-TT-5: Humble Object Testing

**Statement**: When a project uses the commands layer (PL-PA-3), command functions
are testable without mocks, subprocesses, or network. Construct context with an
in-memory protocol implementation, call the command function directly, assert on
result fields.

**Criterion**:
- Pass: command tests run in milliseconds; no subprocess spawning
- Fail: command tests require a running server or subprocess

**Tooling**:
- Test runtime: command tests should complete in < 100ms each
- Reference: biff commands tests with `LocalRelay(tmp_path)`

## PL-TT-6: No Skipping, No Ignoring

**Statement**: If a test fails, fix it. Do not skip, ignore, or work around it.
`@pytest.mark.skip` and `@pytest.mark.xfail` are temporary — they must include
a reason and a bead ID for the fix.

**Criterion**:
- Pass: zero `@pytest.mark.skip` without a tracked issue
- Fail: skipped tests without justification; xfail used permanently

**Tooling**:
- Grep: `grep -rn "pytest.mark.skip\|pytest.mark.xfail" tests/`
