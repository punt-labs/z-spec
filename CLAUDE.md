# z-spec

Part of [Punt Labs](https://github.com/punt-labs). This repo must be checked out inside the `punt-labs/` workspace meta-repo so that org-wide configuration loads via Claude Code's ancestor directory walk:

- **`punt-labs/CLAUDE.md`** — org workflow, delegation model, beads issue tracking, tool configuration
- **`punt-labs/.claude/rules/python-*.md`** — Python OO coding rules, scoped via `paths:` frontmatter (load on-demand when `.py` files are touched)
- **`punt-labs/.envrc`** — git identity, beads DB connection, API keys from platform keychain
- **`punt-kit/standards/`** — canonical reference docs

If cloned outside the workspace, these rules and configuration will not be present.

**OO Python standards adopted 2026-05-13.** The codebase does not yet fully comply. Every commit must improve OO scores (`make check-oo`), never regress. Do not match existing code patterns that violate the rules — write new code to the standard and improve touched files incrementally.

Formal Z specification toolkit: a `fuzz`/`probcli` wrapper, an MCP server, a CLI, and a Claude Code plugin whose skill prompts guide spec creation, type-checking, and animation. Deterministic work — parsing, binary wrappers, report I/O, lux rendering — lives in the Python package; skills call its MCP tools instead of raw bash.

- **Package**: `punt-z-spec` (PyPI). Always `punt-{exact-repo-name}`.
- **CLI**: `z-spec`
- **MCP server**: `zspec` (stdio; `z-spec mcp`)
- **Python**: 3.13+, managed with `uv`

## Mandatory Reading

Source-of-truth documents, `@`-imported so they load into context at session
start. Read them before writing code.

@docs/WORKFLOW.md
@TESTING.md
@../punt-kit/standards/architecture.md
@../punt-kit/standards/oo.md
@../punt-kit/standards/python.md

`WORKFLOW.md` is the three-loop development process (backlog → PR → mission),
with pseudocode and an entry/exit Z schema at each level. `TESTING.md` is the
five-tier pyramid whose top tier — user acceptance testing against the installed
artifact — gates the PR. The `punt-kit/standards` imports are the org's
canonical engine-and-clients architecture, object-oriented stance, and Python
standard, including the ratchet suite this repo runs — cross-repo (external)
imports, so the first load may ask for approval.

## Read This First

**`make check` passing is not evidence that a feature works.** It means the code
compiles, the types hold, the unit tests pass, and every spec in `examples/`
type-checks and model-checks. It says nothing about what a person sees when they
run the CLI, call the MCP tool, or click the lux menu entry.

The verification of record for every user-facing surface is **the feature
running in the installed artifact, exercised by hand, compared against expected
behavior written in advance** — before the PR opens. That is
[`docs/testing/manual-tests.md`](docs/testing/manual-tests.md), reached by
`make uat`. PR #82 shipped to review with a picker full of pytest scratch files,
tabs labelled with truncated paths, an empty content pane, and a Tutorial stuck
on "Loading…" — every one visible the first time a human ran it, none catchable
by a review agent.

The inner loop, run continuously while developing an interactive feature and not
as a final packaging step:

```bash
make check      # gates 1–4
make uat        # build wheel + uv tool install --force dist/*.whl
                # then RECONNECT the z-spec MCP server — a reinstall does not
                # restart a running stdio server, and a stale server demos old code
```

## Architecture

z-spec is one engine with two client surfaces. The engine is the command layer;
the clients are the CLI and the MCP server. Neither client holds business logic
— both resolve the same `Command` objects out of `commands/registry.py`, which
is why `tests/commands/test_parity.py` can assert they cannot drift.

```text
z-spec CLI (__main__.py) ─┐
                          ├─→ commands/registry.py ─→ Command ─→ fuzz.py / prob.py / report.py
zspec MCP (server.py)  ───┘                                  └─→ display.py ─→ lux Hub
```

### Key architectural boundary: commands vs. surfaces

A **command** owns one capability end to end: validate its inputs, invoke the
binary or the store, and return a `CommandResult`. It never prints, never raises
for expected failure, and never knows which surface called it. A **surface**
(CLI verb, MCP tool) translates arguments in and formats results out. A feature
that exists on one surface only is a defect, not a partial delivery.

The lux integration is a third boundary: `display.py` is the only module that
publishes scenes to the Hub, and `lux/` is the receive leg — the session,
identity, menu registration, and click dispatch owned by the MCP server's
FastMCP lifespan. Rendering builders (`applet.py`, `browser.py`) produce element
trees and know nothing about transport.

### Module map

| Module | Responsibility |
|--------|---------------|
| `__main__.py` | Typer CLI — the verb surface |
| `server.py` | FastMCP server (key: `zspec`) — the tool surface; owns the lux session lifespan |
| `commands/registry.py` | The canonical capability list and each capability's name on each surface |
| `commands/*.py` | One command per capability: `check`, `test`, `animate`, `model_check`, `report`, `partition`, `audit`, `show`, `browse`, `picker`, `doctor` |
| `commands/result.py` | `CommandResult` — the envelope every command returns |
| `commands/options.py` | Parameter bundles for the probcli-backed commands |
| `fuzz.py` | Wrapper for the `fuzz` type-checker |
| `prob.py` | Wrapper for the `probcli` model checker |
| `parser.py` | LaTeX Z specification parser → `SpecModel` |
| `report.py` | Report I/O — `<stem>.<type>.json` beside the `.tex` |
| `manifest.py` | Tutorial collection manifests (`manifest.toml`) |
| `display.py` | `LuxDisplay` — the one module that publishes scenes to the lux Hub |
| `applet.py` | Builds a single spec's tabbed lux scene |
| `browser.py` | Builds a collection's tabbed scene and the spec picker |
| `lux/session.py` | `ZSpecLuxSession` — the per-process menu session the lifespan owns |
| `lux/identity.py` | Per-session app identity and its menu labels (**name must be ASCII**) |
| `lux/clients.py` | REST and hub-listener clients built from one identity |
| `lux/menu.py`, `lux/subscription.py`, `lux/command_ports.py`, `lux/ports.py` | Menu registration, the receive leg, and its transport protocols |
| `lux/project.py` | `ProjectRoot` — the user's open project for a plugin-launched server |
| `types/` | Domain types: `spec`, `fuzz`, `prob`, `partition`, `audit`, `reports`, `tutorial` |

### Plugin structure

| Path | Responsibility |
|------|---------------|
| `.claude-plugin/plugin.json` | Manifest; dev tree carries `"name": "z-spec-dev"`, MCP server `zspec` runs `uv run --directory ${CLAUDE_PLUGIN_ROOT} z-spec mcp` |
| `commands/` | Slash commands — each prod command has a generated `-dev` twin (`make gen-dev-commands`, gated by `make check-dev-commands`) |
| `hooks/` | Session hooks |
| `examples/` | The spec corpus — type-checked and model-checked by `make check` |
| `templates/preamble.tex` | Minimal LaTeX preamble for new specs |
| `tutorials/` | Tutorial lesson collections |

`ZSPEC_PLUGIN_ROOT` resolves the tutorial manifest in an installed plugin; a
standalone wheel install needs `importlib.resources` packaging (bead
`z-spec-9v6`).

## Code Quality

Three ratchets, adopted **verbatim from vox** — the canonical implementation for
Python projects at Punt Labs. The tool sources under `tools/oo_ratchet/`,
`tools/coupling/`, and `tools/suppression/` are byte-identical to vox's; keep
them that way. Fixes go to vox first and are re-copied here, never patched in
place. (`tools/*` carries one ruff per-file ignore in `pyproject.toml` for
exactly this reason.)

**OO ratchet:** `make check-oo` (part of `make check`) compares current OO scores
against `.oo-baseline.json`. It passes only if no metric regressed on touched
files **and at least one metric improved**. It fails if any metric got worse or
nothing improved. `make check-coupling` and `make check-suppressions` are the
same discipline for module coupling and for `# noqa` / `# type: ignore` counts.

**Do not negotiate with the ratchet.** Do not edit `.oo-baseline.json` by hand
except via `--rebaseline` for structural refactors. Do not suppress `check-oo`.
If the ratchet fails, improve the code until it passes.

**"No metric improved" means do a good deed, not a rebaseline.** When
`check-oo` reports *"no metric improved on any touched file,"* the ratchet is
telling you this change grew or churned code without paying anything down. The
correct response is a **genuine improvement** — extract a god-method, split an
oversized module, collapse a conditional forest, in a touched file *or*
unrelated nearby debt — **never** a blanket `--rebaseline` to escape the gate.
`--rebaseline` for a structural refactor is **not** a substitute for the
paydown: even a large feature commit must leave at least one metric genuinely
better. Distinguish a **scoped** rebaseline — only the specific `file+metric`
entries that must grow to carry real feature substance, each with a one-line
justification of *why* it is unavoidable, and every *improved* metric left at
its old baseline so it registers as IMPROVED — from a **blanket** rebaseline
that records all growth and retires no debt. The blanket form is the negotiation
this section forbids. When you rebaseline `.oo-baseline.json`, check
`.oo-coupling-baseline.json` too — a structural change often grows coupling.

**The ratchet is tech-debt paydown — make medium-scale improvements, do not
squeeze under the limit.** It exists to retire OO and complexity debt across the
whole codebase a little at a time, the way you amortize a loan. This is
deliberately counterintuitive: it means taking on scope *beyond* the immediate
task, and that added scope is the point. When you touch a file, make a
*substantive* improvement to it — extract a class, break up a god method,
replace a primitive-obsessed signature with a type — not the smallest metric
nudge that scrapes past the gate. Gaming the minimum burns more time than a real
improvement and retires no debt. **Never game a size or complexity metric by
stripping comments or docstrings** — `module_size` is retired by extracting
classes and splitting modules, never by compressing prose.

**Org standards override review tools.** Copilot, Bugbot, and Cursor are
advisory. When a review suggestion conflicts with `../.claude/rules/python-*.md`,
the rules win. Read the rules before accepting a reviewer's suggestion.

**Verify outputs, not just metrics.** After writing a file, open it and read the
content. `make check` passing does not mean the feature works.

Workflow:

1. Write code that improves OO quality on the files you touch.
2. `make check` runs the three ratchets automatically. If one fails, fix the
   regression.
3. After all checks pass, run `make update-oo` (and `update-coupling` /
   `update-suppressions` if those moved).
4. Stage the baselines and audit logs with your commit — they are committed
   files.

Targets: `make check-oo`, `make update-oo`, `make check-coupling`,
`make update-coupling`, `make check-suppressions`, `make update-suppressions`,
`make report` (full diagnostics, no fail-fast), `make metrics` (ABC complexity),
`make coverage` (HTML report).

## Development Loop

The development workflow is **three nested loops** — the **backlog loop** (what
to work on and in what order), the **PR loop** (one rollback-coherent merge), and
the **mission loop** (one delegated piece of work) — defined authoritatively in
**[`docs/WORKFLOW.md`](docs/WORKFLOW.md)**, `@`-imported above so it loads at
session start. Read it before any code change.

The z-spec-specific precision: `make check` green before every commit;
`make uat` **and an MCP server reconnect** before exercising any MCP, slash
command, or lux menu path, because a reinstall does not restart a running stdio
server; the local review agents (`code-reviewer` and `silent-failure-hunter`)
iterated to a zero-findings round; and the **acceptance flight run by hand
before the PR opens** ([`docs/testing/manual-tests.md`](docs/testing/manual-tests.md)),
because no review agent can see an empty pane. Merge mechanics and recap-email
discipline are in the org workflow (`../CLAUDE.md`).

### PR boundaries

Split by **rollback granularity**, not size. If this broke production, what
reverts together? That is one PR. "The diff is large" and "separate concern" are
prohibited split reasons — independent rollback capability and sequential
dependency are the only valid ones.

**One branch, one PR.** A design step is a commit in the PR that implements it,
never a separate design branch with its own doc-PR and review cycle. Do not
review until it works.

**PRs do not need to be "pure," and purity is never a reason to hold back an
improvement.** These PRs are agent-reviewed and squash-merged. A docs tweak, a
ratchet paydown, or an adjacent bug fix riding along with a feature is welcome.
The one real constraint is mechanical: when multiple agents share one worktree,
sequence them so no one's work is clobbered.

## Testing

Five tiers, defined in **[`TESTING.md`](TESTING.md)**, `@`-imported above.

| Tier | Command | In CI | Proves |
|------|---------|-------|--------|
| Unit | `make test-py` | no | each module in isolation |
| Spec type-check | `make type` | no | every `examples/*.tex` is fuzz-clean |
| Spec model-check | `make test` | no | probcli finds no counterexample |
| Surface parity | `test_parity.py` | no | CLI verb and MCP tool resolve to one command |
| **Acceptance (UAT)** | `make uat` + the flight | no — a human | the installed CLI, the reconnected server, and the lux window do the right thing |

**Nothing but markdownlint runs in CI.** There is no `test.yml` or `lint.yml` —
only `docs.yml`, `release.yml`, and `biff-notify.yml`. A green PR attests to the
markdown and nothing else, so the local `make check` is the only real gate.
There is also no subprocess/E2E tier: no test runs the installed binary or drives
the MCP server over stdio. Both gaps are recorded in `TESTING.md`.

**UAT runs before the PR, not after.** `-bad.tex` specs are deliberate
anti-pattern demonstrations, excluded from the gates by the `SPECS` filter in
the Makefile — only use that suffix for specs designed to fail.

## Z Reference Materials (Quarry)

The **`z-specification`** Quarry collection is the authoritative Z reference
library: the Z textbook (`zedbook.pdf`), the fuzz manual (`fuzzman.pdf`),
Bowen's formal specs guide, lecture and semantics slides, exercises, solutions,
and course notes.

**Use Quarry (`mcp__quarry__search_documents` with `collection:
"z-specification"`) to ground every Z decision.** Before writing schemas,
choosing conventions, or answering questions about Z notation, search this
collection. Training-data Z is unreliable.

### Z conventions (ProB-compatible)

These constraints are intentional — do not "modernize" them:

- `\quad~` for continuation lines inside `\begin{zed}`; fuzz does not support `\t1`.
- `ZBOOL ::= ztrue | zfalse`, not a native Bool.
- Optional values as `\finset X` with `\# x \leq 1`.
- `maxFoo : \nat` bounds so ProB can animate.
- Two-letter lowercase free-type prefixes (`sp` for SessionPhase, `tp` for
  ToolPhase) to avoid B keyword conflicts.
- Flat schemas; avoid B keyword collisions.

## Ethos & Delegation

Identity: `agent: claude` per `.punt-labs/ethos.yaml`. Sub-agent calls
(`Agent(subagent_type=…)`) match ethos identity handles. All code delegation
uses ethos missions; **dispatch is two operations** — `ethos mission create`
writes the contract, a separate `Agent(..., run_in_background=true)` starts the
worker.

**The COO does not write code.** The only files the leader edits directly:
`CHANGELOG.md`, `CLAUDE.md`, `README.md`, `TESTING.md`, `docs/WORKFLOW.md`,
design docs, and plan files. **The COO must not read implementation files before
writing a design spec** — a predetermined write-set prevents the specialist from
extracting or restructuring.

**One mission = one task.** Never give an agent multiple steps in a single
prompt.

**No migration, backwards-compatibility, shim, or version-compat code — ever.**
Punt Labs products have no installed user base to migrate. When a feature
supersedes an old behavior, DELETE the old path in the same change. The leader
strikes any such element from a design **before** dispatching implementation.

z-spec's specialists are Z's foundational authors: **jms** (Mike Spivey, *The Z
Notation Reference Manual*, the `fuzz` type-checker) and **jra** (Jean-Raymond
Abrial, originator of Z and the B method). They hold authority on notation,
typing rules, and proof obligations. Beneath them sit the Python and CLI
specialists who ship the deterministic layer. Within each row the worker and
evaluator are distinct; Claude is the leader, never the evaluator.

| Task type | Worker | Evaluator |
|-----------|--------|-----------|
| Z schema authoring (`.tex` Z spec content) | `jms` (Spivey) | `jra` (Abrial) |
| Z notation choices (operators, conventions, idioms) | `jms` | `jra` |
| Refinement / B-method / proof obligations | `jra` | `jms` |
| Typing rules / fuzz type-checker semantics | `jms` | `jra` |
| ProB-compatibility constraints (bounded ints, flat schemas) | `jra` | `jms` |
| Skill prompts (`skills/`, `commands/`) | `jms` | `adt` (Hopper) |
| Python: parsing, binary wrappers, report I/O, commands | `rmh` (Hettinger) | `gvr` (van Rossum) |
| MCP tool surface (`server.py`) | `rmh` | `mdm` (Pike) |
| CLI surface (`__main__.py`) | `mdm` | `rmh` |
| Lux rendering (`applet.py`, `browser.py`, `display.py`) | `edt` (Tufte) | `dna` (Norman) |
| Lux receive leg (`lux/` session, menu, subscription) | `rmh` | `edt` |
| Plugin packaging / dev-prod swap / marketplace | `mdm` | `adb` (Lovelace) |
| Quarry `z-specification` collection / sync | `adb` | `rmh` |
| Test infrastructure and fixtures | `rmh` | `gvr` |

Use the `formal` pipeline for any spec change — type-check with fuzz, animate
with probcli, attach the report. Use `standard` for Python or skill-prompt
changes. Use `quick` only for typo fixes that do not touch a schema.
Review-cycle fix rounds (Copilot/Bugbot findings) use bare `Agent()`, not
missions.

## Release

`punt-z-spec` publishes to PyPI and the plugin ships to the marketplace. The
plugin uses dev/prod namespace isolation — the working tree carries
`"name": "z-spec-dev"` in `plugin.json`.

```bash
uv tool install --force --editable .   # editable install (z-spec = working tree)
claude --plugin-dir .                   # load dev plugin as z-spec-dev
```

Release scripts: `scripts/release-plugin.sh` (swap `z-spec-dev` → `z-spec`),
`scripts/restore-dev-plugin.sh` (restore dev state after tag). Every prod
slash command has a generated `-dev` twin — regenerate with
`make gen-dev-commands`; `make check-dev-commands` fails the gate if they drift.

## Documentation Discipline

### CHANGELOG

Entries are written in the PR branch, before merge — not retroactively on main.
If a PR changes user-facing behavior and the diff does not include a CHANGELOG
entry, the PR is not ready to merge. [Keep a
Changelog](https://keepachangelog.com/en/1.1.0/) format under `## [Unreleased]`.

### README

Update `README.md` when user-facing behavior changes — new flags, commands,
defaults, config, or spec conventions.

### PR/FAQ

Update `prfaq.tex` when the change shifts product direction or
validates/invalidates a risk assumption.

## Pre-PR Checklist

- [ ] `make check` green — full output read, never piped through `tail`/`grep`
- [ ] `make uat` run, MCP server reconnected, **every applicable row of
      `docs/testing/manual-tests.md` executed and matching its written-in-advance
      expectation**
- [ ] Local review clean — `code-reviewer` and `silent-failure-hunter` both
      return zero findings
- [ ] CHANGELOG entry in the diff under `## [Unreleased]`
- [ ] README updated if user-facing behavior changed
- [ ] `prfaq.tex` updated if product direction shifted

## Issue Tracking

Beads (`bd`). If an issue affects multiple repos or requires a standards change,
escalate to a [punt-kit bead](https://github.com/punt-labs/punt-kit) instead.

## Key Documents

- [`docs/WORKFLOW.md`](docs/WORKFLOW.md) — the three-loop development process
- [`TESTING.md`](TESTING.md) — the five-tier pyramid
- [`docs/testing/manual-tests.md`](docs/testing/manual-tests.md) — the acceptance flight
- `README.md` — user-facing surface
- `CHANGELOG.md` — release history
- `prfaq.tex` → `prfaq.pdf` — product direction
- `examples/*.tex` — the spec corpus, gated by `make check`

## Quarry

Local semantic search. Slash commands: `/find`, `/ingest`, `/remember`,
`/explain`, `/source`, `/quarry`. The working directory is auto-indexed at
session start; the `z-specification` collection is the Z reference library
described above.
