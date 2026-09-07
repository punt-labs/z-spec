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
- Z notation conventions (ProB-compatible) — sourced from
  `.rulesync/rules/z-conventions.md`. Claude Code
  loads it only when you touch a `.tex` spec or anything under `examples/`
  (its `paths:`-scoped `.claude/rules/` mechanism honors the glob); codexcli
  and pi have no per-file scoping and instead get it folded into the shared
  root `AGENTS.md`, so it is always in context for those two tools. See the
  rule file's own scoping caveat for the full picture.
- **`permissions` was piloted here and rejected — do not re-add it without
  reading this first.** Rulesync's `permissions` feature (bash/read/edit
  allow-ask-deny policy, projected from `.rulesync/permissions.jsonc`) was
  tried against claude/codex/opencode/pi and mistranslated on 2 of 4 tools:
  Claude Code's generated space-form bash pattern (`"git *"`) never matched
  its Bash matcher (needs `Bash(git:*)`), and codex's generated allow
  `prefix_rule`s were shadowed by its own generated catch-all `prompt` rule
  (codex keeps the most-restrictive decision when multiple rules match a
  command). A generator whose output looks correct but silently does not
  enforce is worse than no generator. See `rulesync.jsonc`'s `targets`
  comment and `CHANGELOG.md` (`[Unreleased]`) for the full record.

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

# Python standards

z-spec follows Punt Labs' org-wide Python standard in full: 22 scoped rule
files (`python-*.md`, one per concern — style, typing, OO ratchet, coupling,
suppression policy, and more) that load automatically by path in any repo
checked out inside the `punt-labs/` workspace meta-repo, from
`../.claude/rules/python-*.md` (ancestor-directory walk, scoped via each
file's own `paths:` frontmatter).

**This rule intentionally does not inline those 22 files.** Per
`punt-kit/standards/context-mgmt.md`, DRY means de-duplicating a single
source of truth, not deleting the reference and hoping the reader already
knows the content — so this file names the dependency explicitly instead of
either copying it stale or silently omitting it.

**Standalone-clone caveat, stated honestly:** if z-spec is checked out on its
own (not as a sibling inside `punt-labs/`), `../.claude/rules/python-*.md`
does not exist and this pointer resolves to nothing. In that case:

- Fetch the canonical set from
  [`punt-kit/standards/python.md`](https://github.com/punt-labs/punt-kit/blob/main/standards/python.md),
  the summary doc that indexes all 22 rule files, or
- Check out inside the `punt-labs/` workspace meta-repo per this repo's own
  `CLAUDE.md`, which is the supported layout and the one CI and every other
  Punt Labs Python repo assumes.

Do not re-derive Python style rules from memory or from a different
project's conventions — the 22-file standard is the one source of truth,
wherever it is reached from.

**Scoping caveat, stated honestly:** the file-selection pattern above
(`**/*.py`) is enforced only for `claudecode`, which reads this file from
`.claude/rules/python-standards-pointer.md` with a `paths:` frontmatter
Claude Code checks per-file. `codexcli` and `pi`
have no modular rules directory to scope against — rulesync folds this
rule's body unconditionally into the shared root `AGENTS.md`, so those two
tools see this Python pointer on every file, not only `**/*.py` (a pointer,
not a style rule itself, so the practical cost is a stale reference visible
outside Python work rather than a misapplied convention). `opencode` is
intentionally left out of `targets` above: its `instructions` array is
project-wide with no glob support either, and rulesync would additionally
register this rule a second time (root `AGENTS.md` plus
`.opencode/memories/python-standards-pointer.md`) since opencode reads both
— a real double-load, not just an unscoped one. Getting the guidance into
AGENTS.md via `codexcli`/`pi` already covers opencode's users; excluding it
from `targets` avoids the duplicate registration without losing coverage.

# Z conventions (ProB-compatible) — do not "modernize"

- `\quad~` for continuation lines inside `\begin{zed}`; fuzz has no `\t1`.
- `ZBOOL ::= ztrue | zfalse`, not a native Bool.
- Two-letter lowercase free-type prefixes to avoid B keyword conflicts.
- Flat schemas; bounded integers so ProB can animate.

**Scoping caveat, stated honestly:** the file-selection patterns above
(`**/*.tex`, `examples/**`) are enforced only for `claudecode`, which reads
this file from `.claude/rules/z-conventions.md` with a `paths:` frontmatter
Claude Code checks per-file. `codexcli` and `pi`
have no modular rules directory to scope against — rulesync folds this rule's
body unconditionally into the shared root `AGENTS.md`, so those two tools
apply these Z conventions to every file, not only `.tex` specs and
`examples/**`. `opencode` is intentionally left out of `targets` above:
its `instructions` array is project-wide with no glob support either, and
rulesync would additionally register this rule a second time (root
`AGENTS.md` plus `.opencode/memories/z-conventions.md`) since opencode reads
both — a real double-load, not just an unscoped one. Getting the guidance
into AGENTS.md via `codexcli`/`pi` already covers opencode's users; excluding
it from `targets` avoids the duplicate registration without losing coverage.
