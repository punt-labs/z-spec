# Testing

## Philosophy

`make check` proves the code is internally consistent. It does not prove the
feature works. Those are different claims, and conflating them is how a feature
reached PR #82 with a spec picker that surfaced pytest scratch files, tabs
labelled with truncated paths, an empty content pane, and a Tutorial stuck on
"Loading…" — every one of which is visible the first time a human runs it.

So the pyramid has five tiers, and the top one is **user acceptance testing done
by a human against the installed artifact, before the PR opens.** UAT is not a
post-merge activity, not a reviewer's job, and not something Copilot or Bugbot
can do. Code reviewers find code defects; only running the thing finds "the
feature is unusable."

## The pyramid

| Tier | Command | Runs in CI | What it proves | Gate |
|------|---------|------------|----------------|------|
| 1. Unit | `make test-py` | yes — `test.yml` `unit` | each module behaves in isolation — parsing, report I/O, command objects, types; and each shipped prompt document is internally consistent | every commit |
| 2. Spec type-check | `make type` (`type-z-*`) | yes — `test.yml` `specs` | every `examples/*.tex` is fuzz-clean; the tool's own corpus type-checks | every commit |
| 3. Spec model-check | `make test` (`test-z-*`) | yes — `test.yml` `specs` | probcli explores each spec's reachable state space, finds no counterexample, certifies the exploration complete, and fires every operation at least once | every commit |
| 4. Surface parity | `tests/commands/test_parity.py` | yes — `test.yml` `unit` | the CLI verb and the MCP tool for one command resolve to the same `Command` object with the same options | every commit |
| 5. **Acceptance (UAT)** | `make uat` + [`docs/testing/manual-tests.md`](docs/testing/manual-tests.md) | the subprocess half only — `test.yml` `e2e` | the installed CLI, the reconnected MCP server, and the lux menu do the right thing on screen | **before the PR opens** |

Tiers 1–4 are `make check`. Tier 5 splits: `make test-e2e` drives the installed
binary and the stdio server and does run in CI, while the human half — the lux
window, the labels, what a person actually sees — is the demo gate in
[`docs/WORKFLOW.md`](docs/WORKFLOW.md) and cannot be automated.

### What CI covers

`.github/workflows/` carries `lint.yml` and `test.yml` alongside `docs.yml`,
`release.yml` and `biff-notify.yml`. `lint.yml` runs ruff check and format, mypy,
pyright, shellcheck, `check-dev-commands`, and all three ratchets scoped to the
merge base via `OO_BASE` / `COUPLING_BASE` / `SUPPRESSION_BASE`, with a
post-merge `HEAD~1` tripwire on main. `test.yml` runs three jobs: `unit`
(pytest), `e2e` (builds and installs the wheel, then drives the installed
artifact), and `specs` (builds `fuzz` from source, downloads `probcli`, then
type-checks and model-checks every `examples/*.tex`).

So a green PR is now evidence. It was not before, and this section previously
said so long after it had stopped being true — the gap sections were written
when they were real, the gaps were closed, and nobody came back to the page. A
"known gap" that has been fixed is worse than no note at all, because it tells a
reader to distrust a gate that works.

The remaining honest caveat is narrower: the ratchets compare against a merge
base, so a branch that never touches Python trivially passes them. That is by
design, not a hole.

### The subprocess tier

`tests/e2e/` drives the `z-spec` binary that `make install` put on `PATH` — not
the working tree. `test_installed_cli.py` runs it as a subprocess (`--version`,
every registry verb in `--help`, a missing spec failing without a traceback,
`check` reaching the real `fuzz`, `doctor` from an unrelated directory) and
`test_installed_mcp.py` drives the MCP server over stdio with a JSON-RPC
`initialize` handshake and `tools/list` asserted against the capability registry.

These catch the packaging faults no in-process test can see: an entry point that
does not resolve, a data file absent from the wheel, a `__file__`-relative path
that only works in a checkout. `pyproject.toml` declares the `e2e` marker and
`addopts` deselects it by default, so a plain `pytest` run does not test whatever
wheel happens to be installed. Run it with `make test-e2e`.

Tests mirror source: one `test_*.py` per module, `tests/commands/` and
`tests/lux/` mirroring their packages, `conftest.py` for shared fixtures.

## Tier 5 — user acceptance testing

**UAT happens before the PR, never after.** The order is: `make check` green →
`make uat` (build, install, reconnect the MCP server) → run every applicable
row of the flight → fix until each row matches → *then* local review agents →
*then* the PR. A PR opened before UAT passes is a procedural violation: it
spends review cycles (minutes to hours each) on code that does not yet do its
job.

Three rules make UAT worth the time:

1. **Write the expected outcome before running.** Not after. Every difference
   between what you wrote and what happened is a bug, including the ones you
   would have rationalized away.
2. **Test the installed artifact, not the working tree.** `make install`
   rebuilds the wheel and installs the `z-spec` CLI. The running MCP server
   holds the old code until it is reconnected — a reinstall does not restart it.
   Testing against a stale server proves nothing about the change.
3. **Look at the screen, not only the introspection API.** For lux surfaces,
   `list_menus` / `list_scenes` / `inspect_scene` / `list_recent_events` /
   `list_errors` give Hub-side truth, and the window gives what the human sees.
   They diverge: a scene can hold 838 elements and render an empty pane. Both,
   every time.

The canonical flight — the matrix of action × context × expected outcome, with
the empty-directory, scratch-directory, installed-plugin, and standalone-CLI
cells that hold the bugs — is [`docs/testing/manual-tests.md`](docs/testing/manual-tests.md).

## What good testing means in this project

z-spec wraps two external binaries (`fuzz`, `probcli`) and exposes them through
two client surfaces (CLI and MCP) plus a lux display. Each of those boundaries
has a characteristic failure:

- **Binary wrappers must test the absent-binary and the non-zero-exit paths.**
  A missing `probcli` or a fuzz type error is normal operating input, not an
  exception the user should see as a traceback. Every wrapper test covers
  success, tool-absent, and tool-failed.
- **Parse tests use real tool output, not invented strings.** fuzz and probcli
  output formats are the contract. A parser test whose fixture was written from
  memory passes while the parser is broken. Capture actual output into the
  fixture.
- **The spec corpus is a test.** `examples/*.tex` is type-checked and
  model-checked by `make check`. A spec that stops being fuzz-clean is a
  regression in the tool's documentation of its own notation. `-bad.tex` files
  are the deliberate exception — anti-pattern demonstrations, excluded from the
  gates by the `SPECS` filter in the Makefile.
- **A specification that a gate reads is stored where its purpose says.**
  `examples/` holds specs a reader should read, including deliberately bad ones
  that teach — `animation-hints-bad.tex` is there to be read. `tests/fixtures/
  probcli/specs/` holds specs a test should execute: `deadlock-bad.tex`,
  `unreachable-operation-bad.tex`, `xi-frame-bad.tex`,
  `covered-then-deadlock-bad.tex` and `hidden-deadlock-bad.tex` exist to make
  the gate go red, and two of them are near-duplicates of a neighbour, which a
  document written to be read would not be. The `-bad` suffix means "excluded
  from the corpus gates," not "lives in `examples/`."
- **A gate must be shown failing before it is trusted.** All five fixture
  specs above are fuzz-clean: every defect they carry passes the type-check
  tier untouched and is visible only at model-check. Each one exists because a
  gate claimed to catch something and did not, and each was written by
  constructing the failure rather than by reading the code — three separate
  attempts were needed to build a specification whose deadlock a truncated
  exploration actually hides, because `MAX_OPERATIONS` is a per-operation
  budget and transitions sharing a successor collapse. A check that has never
  been observed failing is a check whose passing means nothing.
- **CLI and MCP must not drift.** Both surfaces run the same `Command` objects
  from `commands/registry.py`. `test_parity.py` asserts that; a command added to
  one surface only is a defect, not a partial feature.
- **Lux code is tested with fakes at the port, and confirmed by eye.** The
  `lux/ports.py` protocols let unit tests drive session, menu, and subscription
  logic without a daemon. That covers the wiring. It does not cover whether the
  scene renders — that is tier 5, always.

## Running tests

`make check` writes `examples/<stem>.report.json` for every spec it checks,
because the gate drives the same `ModelCheckCommand` the CLI verb and MCP tool
resolve, and that command persists its report. The files are gitignored and
`make clean` removes them. It is worth knowing rather than discovering: after a
`make check` the reports on disk correspond to the code that just ran, where
before they corresponded to whenever someone last ran `make spec-reports`.

```bash
make check          # tiers 1–4: lint, types, fuzz, pytest, probcli, ratchets
make test-py        # unit tests only
uv run pytest tests/commands/test_picker.py -v   # one file
uv run pytest -k picker                          # one pattern
make coverage       # terminal + HTML coverage (htmlcov/index.html)
make report         # every gate and metric, no fail-fast
make uat            # build + install, then run docs/testing/manual-tests.md
```

## Quality gates

`make check` runs, in order: `lint` (markdownlint + ruff check + ruff format),
`type` (mypy + pyright + fuzz on every spec), `test` (pytest + probcli on every
spec), `check-oo`, `check-coupling`, `check-suppressions`, `check-dev-commands`.

The three ratchets are adopted verbatim from vox, the canonical implementation.
`check-oo` passes only if no metric regressed on touched files **and at least
one improved** — see the OO ratchet section of [`CLAUDE.md`](CLAUDE.md) for what
that demands and what it forbids. Coverage never goes down; the test count never
goes down.

No suppression (`# noqa`, `# type: ignore`, `xfail`, `--no-verify`) is added to
make a gate pass without operator approval, outside the classes pre-authorized
by the org standards.
