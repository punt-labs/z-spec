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
| 1. Unit | `make test-py` | **no** | each module behaves in isolation — parsing, report I/O, command objects, types | every commit |
| 2. Spec type-check | `make type` (`type-z-*`) | **no** | every `examples/*.tex` is fuzz-clean; the tool's own corpus type-checks | every commit |
| 3. Spec model-check | `make test` (`test-z-*`) | **no** | probcli explores each spec's reachable state space with no counterexample | every commit |
| 4. Surface parity | `tests/commands/test_parity.py` | **no** | the CLI verb and the MCP tool for one command resolve to the same `Command` object with the same options | every commit |
| 5. **Acceptance (UAT)** | `make uat` + [`docs/testing/manual-tests.md`](docs/testing/manual-tests.md) | no — a human runs it | the installed CLI, the reconnected MCP server, and the lux menu do the right thing on screen | **before the PR opens** |

Tiers 1–4 are `make check`. Tier 5 is the demo gate in
[`docs/WORKFLOW.md`](docs/WORKFLOW.md) — the one human step in the loop.

### Known gap: none of this runs in CI

`.github/workflows/` contains `docs.yml` (markdownlint), `release.yml`, and
`biff-notify.yml`. **There is no test or lint workflow.** On a pull request, the
only check that runs is markdownlint — so "CI green" in the merge gate currently
attests to nothing but the markdown. Tiers 1–4 are enforced by discipline at the
local `make check`, not by the platform.

vox has `test.yml` and `lint.yml`; z-spec needs the same, plus the ratchet gates
with their `--base-ref <merge-base> --require-base` flags (the `OO_BASE`,
`COUPLING_BASE`, `SUPPRESSION_BASE` Makefile variables exist for exactly this and
are unused). Until those workflows land, do not treat a green PR as evidence.

### Known gap: no subprocess/E2E tier

Nothing in `tests/` runs the installed `z-spec` binary as a subprocess or drives
the MCP server over stdio. `tests/test_main.py` uses Typer's in-process
`CliRunner`; `tests/test_fuzz.py`, `test_prob.py`, and `test_server.py` patch
`subprocess.run` and assert against hand-written `CompletedProcess` output. That
means the wire between the installed artifact and its process boundary — argv
parsing, exit codes, stdio framing, packaged data files — is covered only by tier
5, by hand. The org standard (`PL-TT-1`) calls for this tier behind a pytest
marker; z-spec has no markers configured at all.

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
- **CLI and MCP must not drift.** Both surfaces run the same `Command` objects
  from `commands/registry.py`. `test_parity.py` asserts that; a command added to
  one surface only is a defect, not a partial feature.
- **Lux code is tested with fakes at the port, and confirmed by eye.** The
  `lux/ports.py` protocols let unit tests drive session, menu, and subscription
  logic without a daemon. That covers the wiring. It does not cover whether the
  scene renders — that is tier 5, always.

## Running tests

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
