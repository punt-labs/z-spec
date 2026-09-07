---
root: true
targets: ["*"]
description: "z-spec project overview and lean index"
globs: ["**/*"]
---

# z-spec

Formal Z specification toolkit: a `fuzz`/`probcli` wrapper, an MCP server
(`zspec`), a CLI (`z-spec`), and a Claude Code plugin whose skill prompts
guide spec creation, type-checking, and animation. Deterministic work —
parsing, binary wrappers, report I/O, lux rendering — lives in the Python
package; skills call its MCP tools instead of raw bash.

Part of [Punt Labs](https://github.com/punt-labs). Must be checked out
inside the `punt-labs/` workspace meta-repo so org-wide configuration
(git identity, beads DB, API keys) loads from `../CLAUDE.md` and `../.envrc`.

- **Package**: `punt-z-spec` (PyPI)
- **CLI**: `z-spec`
- **MCP server**: `zspec` (stdio; `z-spec mcp`)
- **Python**: 3.13+, managed with `uv`

## Architecture

One engine, two thin client surfaces (CLI + MCP), both resolving the same
`Command` objects from `commands/registry.py` — `tests/commands/test_parity.py`
asserts they cannot drift. A command validates inputs, invokes the binary or
store, and returns a `CommandResult`; it never prints and never knows which
surface called it. `display.py` is the only module that publishes scenes to
the lux Hub.

## Build and test commands

```bash
make check      # full quality gate: lint, type, test, check-oo,
                 #   check-coupling, check-suppressions, check-dev-commands
make lint       # markdownlint + ruff check + ruff format --check + shellcheck
make type       # mypy + pyright + fuzz on every examples/*.tex spec
make test       # pytest + probcli model-check on every examples/*.tex spec
make uat        # build wheel, install CLI, then run the acceptance flight
                 #   by hand — RECONNECT the MCP server after; a reinstall
                 #   does not restart a running stdio server
make check-oo   # OO ratchet: must improve over baseline, never regress
```

`make check` passing means the code compiles, types hold, unit tests pass,
and every spec type-checks and model-checks. It is necessary, never
sufficient — it says nothing about what a person sees running the CLI,
calling the MCP tool, or clicking the lux menu entry. The verification of
record for every user-facing surface is the feature running in the
installed artifact, exercised by hand against a written-in-advance
expectation, before the PR opens.

## Where to look for more

- [`docs/WORKFLOW.md`](docs/WORKFLOW.md) — the three-loop development
  process (backlog → PR → mission), with pseudocode and entry/exit Z
  schema at each level. Read before any code change. PR sizing/boundary
  rules are stated there as `EnterPR`/`ExitPR` (rollback coherence,
  throughput band); see also
  [`../punt-kit/standards/pr-review.md`](../punt-kit/standards/pr-review.md)
  § PR Boundaries for the org-wide statement of the same rule (split by
  rollback granularity, not size or "separate concern").
- [`TESTING.md`](TESTING.md) — the five-tier testing pyramid; tier 5
  (acceptance/UAT) gates the PR and cannot be automated.
- [`docs/testing/manual-tests.md`](docs/testing/manual-tests.md) — the
  acceptance flight run by `make uat`.
- [`docs/development.md`](docs/development.md) — dev/prod plugin
  namespace isolation, release flow, the `plugin/` project structure and
  its two load-bearing boundary rules (`${CLAUDE_PLUGIN_ROOT}` scoping),
  the `ZSPEC_PLUGIN_ROOT` env var and its standalone-wheel-install
  caveat (bead `z-spec-9v6`), and the module-by-module responsibility map
  for `src/punt_zspec/`.
- [`../punt-kit/standards/architecture.md`](../punt-kit/standards/architecture.md)
  — the org's canonical engine-and-clients projection model.
- [`../punt-kit/standards/oo.md`](../punt-kit/standards/oo.md) — the
  language-agnostic object-oriented stance.
- [`../punt-kit/standards/python.md`](../punt-kit/standards/python.md) —
  the Python standard, including the OO/coupling/suppression ratchet
  suite this repo runs. [`docs/development.md`](docs/development.md)
  § "The OO ratchet: a good deed, not a rebaseline" adds the operational
  nuance the standard states tersely — the good-deed-not-rebaseline rule,
  and the scoped-vs-blanket-rebaseline distinction with per-entry
  justification comments.
- [`../punt-kit/standards/workflow.md`](../punt-kit/standards/workflow.md)
  § "Documentation in the diff" — CHANGELOG entries land in the PR diff,
  under `## [Unreleased]`, Keep a Changelog format.
- [`../punt-kit/standards/readme.md`](../punt-kit/standards/readme.md) —
  when and how to update `README.md`; this repo's own README is cited
  there as a reference implementation.
- `prfaq.tex` — update when a change shifts product direction or
  validates/invalidates a risk assumption. Not covered by any punt-kit
  standard; the org-wide statement of this rule lives one directory up,
  in the workspace meta-repo's own `CLAUDE.md` § Documentation Discipline
  → PR/FAQ, loaded via Claude Code's ancestor-directory walk when this
  repo is checked out inside `punt-labs/` (see
  `../punt-kit/standards/context-mgmt.md` § 7 on global config, and the
  checkout requirement stated above).
- `README.md` — user-facing surface. `CHANGELOG.md` — release history.
  `examples/*.tex` — the spec corpus gated by `make check`.
- Z notation conventions (ProB-compatible) — see
  `.rulesync/rules/z-conventions.md` rather than a copy here. Claude Code
  loads it only when you touch a `.tex` spec or anything under `examples/`
  (its `paths:`-scoped `.claude/rules/` mechanism honors the glob); codexcli
  and pi have no per-file scoping and instead get it folded into the shared
  root `AGENTS.md`, so it is always in context for those two tools. See the
  rule file's own scoping caveat for the full picture.

## Code quality

Three ratchets — OO, coupling, suppression — adopted verbatim from vox, the
canonical implementation. `make check-oo` passes only if no metric regressed
on touched files and at least one improved. Never edit `.oo-baseline.json` by
hand except `--rebaseline` for structural refactors; never suppress the
ratchet. Org standards (see `../punt-kit/standards/python.md` above) override
review-tool suggestions (Copilot, Bugbot, Cursor) when the two disagree.

No migration, backwards-compat, or shim code — ever; when a feature
supersedes an old behavior, delete the old path in the same change.

## Issue tracking

Beads (`bd`). Escalate to a punt-kit bead if an issue spans repos or needs a
standards change.
