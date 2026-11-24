# Testing

This guide follows the [Punt Labs testing standard](https://github.com/punt-labs/punt-kit/blob/main/standards/testing.md)
and its [Python mapping](https://github.com/punt-labs/punt-kit/blob/main/lang-rules/python/python-testing.md).

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

## Triggers and budgets

Provision Python 3.13, Git, and uv, then run `uv sync --frozen --all-extras`.
Run `make hooks` to activate the local gates. It preserves other Git hooks
and leaves linked worktrees without these test commands unaffected. If the
repo already has a custom pre-commit hook, invoke `.githooks/pre-commit`
from it. To chain a custom pre-push hook, move it aside and replace the
installed pre-push entry point with an executable wrapper:

```bash
#!/usr/bin/env bash
chain=/path/to/custom-hook
if [[ -x .githooks/pre-push ]]; then
  exec .githooks/pre-push --chain "$chain" "$@"
fi
printf '%s\n' 'z-spec pre-push gate not present in this worktree; skipping it.' >&2
exec "$chain" "$@"
```

Point `/path/to/custom-hook` at the hook you moved. Both hooks then receive
the same list of refs. Don't run `make hooks` to install this wrapper.
The hook targets use system temporary storage rather than the checkout's
`.tmp`.
For direct local pytest runs under direnv, use `--basetemp` with a dedicated
path outside the checkout.

| Tier | Runner and selector | Budget | Failure |
| --- | --- | --- | --- |
| Pre-commit | Local hook: `make test-changed` selects default tests by staged path and source imports. Changes to shared fixtures or source with indirect or unknown consumers fall back to the default suite. | <30 s for typical small changes | Stops commit |
| Pre-push | Local hook: `make test-push` runs the default suite, including credential-free local process contracts. | <3 min | Stops push |
| PR | GitHub Actions: Docs, Lint and Test. Test uses Ubuntu and macOS for default, installed wheel, spec corpus and installer checks. | <10 min target for the parallel gate | Required checks block merge |
| Merge to main | The same workflows validate the actual main commit and publish default coverage. | Same PR budget | Red main triggers CI triage |
| Nightly | Ubuntu, upstream main only: `nightly.yml` / `make test-nightly` reruns the installed wheel on main, and explores the animation-hints model at set size 2 rather than 1. Prerequisites: wheel, Git, `fuzz`, and `probcli`. | 30 min job timeout | Biff notifies maintainers; not a PR check |
| Release candidate | Ubuntu, trusted release CI: exact TestPyPI wheel and both installed entry points. | 10 min job timeout | Blocks promotion |
| Post-release | Ubuntu, trusted release CI: exact production PyPI version and both installed entry points. | 2 min job timeout | Alerts the release owner |

The default suite (`make test-py`) runs in-process unit/component tests and
local subprocess tests; `make test-subprocess` selects the installer pin and
command-tool process contracts separately. `make test-e2e` selects installed
CLI/MCP workflows. `make type` and `make test` include the domain checks:
`type-z-*` checks specs with `fuzz`; `test-z-*` checks reachability, absence
of counterexamples, completeness and operation coverage with `probcli`.
The credential-free gates require no provider credentials or running daemons.

The deterministic CLI/MCP operations do not require a live provider. The
Claude plugin does need real-agent evidence; currently its applicable rows are
covered by manual UAT, not an automated trusted Nightly or candidate gate.
Manual installed-artifact UAT remains the separate change-level demo gate in
[`docs/WORKFLOW.md`](docs/WORKFLOW.md).

### What CI covers

`.github/workflows/` carries `lint.yml` and `test.yml` alongside `docs.yml`,
`nightly.yml`, `release.yml` and `biff-notify.yml`. `lint.yml` runs ruff check and format, mypy,
pyright, shellcheck, `check-dev-commands`, the design gate against the PR base,
and the OO, coupling and suppression ratchets scoped to the merge base via
`OO_BASE` / `COUPLING_BASE` / `SUPPRESSION_BASE`, with a post-merge `HEAD~1`
tripwire on main. `test.yml` runs `unit`
(pytest), `e2e` (builds and installs the wheel, then drives the installed
artifact), `specs` (builds `fuzz` from source, downloads `probcli`, then
type-checks and model-checks the example corpus), and `installer` (both
supported platforms, with and without TeX).

So a green PR is now evidence. It was not before, and this section previously
said so long after it had stopped being true — the gap sections were written
when they were real, the gaps were closed, and nobody came back to the page. A
"known gap" that has been fixed is worse than no note at all, because it tells a
reader to distrust a gate that works.

The remaining honest caveat is narrower: the ratchets compare against a merge
base, so a branch that never touches Python trivially passes them. That is by
design, not a hole.

### The subprocess tier

`tests/e2e/` drives the `z-spec` binary that `make install` put in uv's tool
directory — not the editable entry point on pytest's `PATH`.
`test_installed_cli.py` runs it as a subprocess (`--version`,
every registry verb in `--help`, a missing spec failing without a traceback,
`check` reaching the real `fuzz`, `doctor` from an unrelated directory) and
`test_installed_mcp.py` drives the MCP server over stdio with a JSON-RPC
`initialize` handshake and `tools/list` asserted against the capability registry.
It also calls the real `check` tool in a temporary enabled repository and
asserts both the tool result and the report it writes.

These catch the packaging faults no in-process test can see: an entry point that
does not resolve, a data file absent from the wheel, a `__file__`-relative path
that only works in a checkout. `pyproject.toml` declares the `e2e` marker and
`addopts` deselects it by default, so a plain `pytest` run does not test whatever
wheel happens to be installed. Run it with `make test-e2e` or
`uv run pytest -m e2e` after `make install`, with Git and real `fuzz` on
`PATH`. Missing prerequisites
fail the suite rather than silently reducing the evidence. Tests copy the
spec into temporary state and do not require ProB or a running Lux daemon.

Tests mirror source: one `test_*.py` per module, `tests/commands/` and
`tests/lux/` mirroring their packages, `conftest.py` for shared fixtures.

### Coverage

`make coverage` reports line and branch coverage in the terminal and at
`htmlcov/index.html`. `make coverage-ci` runs the same selection and
generates `coverage.xml`; PR and main CI publish successful reports per
commit and OS. Coverage includes `punt_zspec` code run in the default
pytest process. It excludes the installed CLI and MCP subprocesses,
external binaries, and manual UAT. There is no percentage floor.

### Release gates

On an Ubuntu runner, `release.yml` fetches the tagged wheel from TestPyPI
and compares its bytes with the build artifact before installing it.
Within the 10-minute candidate job, the installed CLI and MCP server
must both type-check a copy of `animation-hints-good.tex` with real
`fuzz`, in a fresh virtual environment and temporary project. A failure
blocks production promotion; PyPI receives the original build artifacts.

Immediately after publication, the Ubuntu smoke job installs the exact
version from production PyPI and runs the same checks with a two-minute
job timeout. Both jobs assert the CLI version and log the version,
channel, and outcome. The release build provides `fuzz`; ProB and a Lux
daemon are not needed. A post-release failure fails the release workflow
and alerts the team on Biff for release-owner triage; publication is not
rolled back automatically.

To reproduce either smoke locally with Python 3.13, `uv`, Git, and
`fuzz` on `PATH`:

```bash
uv build
bash scripts/smoke-release.sh candidate VERSION dist/punt_z_spec-VERSION-py3-none-any.whl
bash scripts/smoke-release.sh published VERSION
```

## Quarantine

Fix flaky tests promptly. If a required test must be isolated, file a Linear
issue with a named owner, reason, and fix-or-remove deadline within 14 days.
Use `@pytest.mark.quarantine(issue=..., owner=..., reason=..., expires=...)`,
with the `PL-...` identifier and a UTC `YYYY-MM-DD` deadline matching the
issue. Required pytest selections exclude the mark, but collection still
fails on incomplete, expired, or overlong metadata.

Nightly runs `make test-quarantine` to list marked tests (an empty list is
valid). Review the list daily, diagnose failures before retrying, and restore
fixed tests to their normal gate. To run quarantines separately, use
`make test-quarantine-run` (or `uv run pytest -m quarantine` for in-process
tests). Install the wheel and provision the relevant tools for installed or
subprocess cases.

## Manual user acceptance testing

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
  scene renders — that is manual UAT.

## Running tests

`make check` writes `examples/<stem>.report.json` for every spec it checks,
because the gate drives the same `ModelCheckCommand` the CLI verb and MCP tool
resolve, and that command persists its report. The files are gitignored and
`make clean` removes them. It is worth knowing rather than discovering: after a
`make check` the reports on disk correspond to the code that just ran, where
before they corresponded to whenever someone last ran `make spec-reports`.

```bash
make check          # lint, types, fuzz, pytest, probcli, ratchets
make test-py        # credential-free default pytest suite
uv run pytest tests/commands/test_picker.py -v   # one file
uv run pytest -k picker                          # one pattern
make coverage       # terminal + HTML coverage (htmlcov/index.html)
make report         # every gate and metric, no fail-fast
make uat            # build + install, then run docs/testing/manual-tests.md
```

## Quality gates

`make check` runs, in order: `lint` (markdownlint + ruff check + ruff format),
`type` (mypy + pyright + fuzz on every spec), `test` (pytest + probcli on every
spec), `check-oo`, `check-coupling`, `check-suppressions`, `check-dev-commands`,
and `design-gate`.

`design-gate` compares `src/punt_zspec` against `DESIGN_BASE` (default
`origin/main`) and rejects would-fail verdicts, tool/input errors, and a
missing or unresolvable base ref. In a clean tree on main, HEAD and the default
base are the same commit, so the comparison is neutral.

The OO, coupling and suppression ratchets run from the pinned PyPI dev package
`punt-oo-ratchet==0.4.0`, installed by `uv sync`.
`check-oo` passes only if no metric regressed on touched files **and at least
one improved** — see the OO ratchet section of [`CLAUDE.md`](CLAUDE.md) for what
that demands and what it forbids. Review coverage changes when adding or
changing behavior; the coverage report is not a percentage gate.

No suppression (`# noqa`, `# type: ignore`, `xfail`, `--no-verify`) is added to
make a gate pass without operator approval, outside the classes pre-authorized
by the org standards.
