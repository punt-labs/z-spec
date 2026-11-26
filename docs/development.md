# Development

This document covers contributor-facing details: how to run the dev plugin
against the working tree, how a release swaps between dev and prod plugin
names, and how the plugin directory is laid out. Most of this only matters if
you are editing z-spec itself.

For quality-gate commands, see [CONTRIBUTING.md](../CONTRIBUTING.md).

## Dev/prod namespace isolation

The working tree is the dev plugin: `plugin/.claude-plugin/plugin.json` has `name: "z-spec-dev"` and
its MCP server runs the working tree via
`uv run --directory ${CLAUDE_PLUGIN_ROOT} z-spec mcp`. The marketplace release
is the prod plugin: `name: "z-spec"` with the MCP server invoking the installed
`z-spec` binary. The two names differ, so both load at once — you get
production commands and working-tree commands side by side.

| Source | Commands | MCP tools | What they run |
|--------|----------|-----------|---------------|
| Marketplace `z-spec` | `/z-spec:check`, `/z-spec:test`, ... | `mcp__plugin_z-spec_zspec__*` | Installed `z-spec` binary |
| Local `z-spec-dev` | `/z-spec-dev:check-dev`, `/z-spec-dev:test-dev`, ... | `mcp__plugin_z-spec-dev_zspec__*` | Working tree (`uv run`) |

The `-dev` command twins are generated, not hand-written. Every prod command
`plugin/commands/<c>.md` has a `plugin/commands/<c>-dev.md` twin identical
except its MCP tool references gain the `-dev` plugin suffix and its
`/z-spec:<cmd>` self-references become `/z-spec-dev:<cmd>-dev`. Regenerate
them after editing any prod command:

```bash
make gen-dev-commands     # rewrite the twins from prod sources
make check-dev-commands   # fail if any twin is missing or stale (part of `make check`)
```

### Local test

From the repo root, with the working tree in dev state:

```bash
uv sync                     # 1. install the working-tree z-spec into the project venv
claude --plugin-dir plugin  # 2. launch Claude Code loading z-spec-dev alongside z-spec
/z-spec-dev:check-dev examples/oracle-protocol.tex   # 3. run a dev command against the working tree
```

`plugin`, not `.`: the plugin root is the `plugin/` directory, so that is the
directory `CLAUDE_PLUGIN_ROOT` must name — the same one a marketplace install
checks out. The dev manifest's `uv run --directory ${CLAUDE_PLUGIN_ROOT}`
still finds this project because uv discovers a project by walking up from the
directory it is given, and `plugin/`'s parent is the repo root.

`/z-spec-dev:*` commands and their `mcp__plugin_z-spec-dev_zspec__*` tools
exercise the code in the working tree; the marketplace `/z-spec:*` commands
stay on the installed release. Nothing is published — the dev plugin is loaded
only for that session.

## Release flow

`release-plugin.sh` performs three swaps in one commit: the plugin name
(`z-spec-dev` → `z-spec`), the MCP server command (`uv run` working tree → the
installed `z-spec` binary, so marketplace users without a uv project can run
it), and it strips the `-dev` command twins. The marketplace hook requires the
`z-spec-hook` entry point from the installed wheel. `restore-dev-plugin.sh` restores
all three by checking out `plugin/.claude-plugin/plugin.json` and `plugin/commands/` from the parent
of the release-prep commit.

```bash
# 1. Prepare release (swaps name + MCP command to prod, removes -dev commands)
bash scripts/release-plugin.sh

# 2. Tag the release — the tag must point at the prod-named commit
git tag v0.1.0
git push origin v0.1.0

# 3. Restore dev state on main
bash scripts/restore-dev-plugin.sh
git push origin main
```

Both scripts abort if the working tree has uncommitted changes.

## Ethos handoff runtime

DES-086 loads `checks/snapshots/<slug>.yaml` beside the winning
`checks/<slug>.yaml` in the same configuration layer. For z-spec, that
sidecar attaches to `full-gate-handoff` without changing its Make adapter
or `check` target. Older Ethos releases that don't recognize sidecars
still run the gate live.

The Linux amd64 snapshot uses the same `make check` target as a live
handoff. It needs a pinned offline bundle and host Bash, Git, Java, Make,
and ShellCheck. To build the bundle, use upstream Node with its bundled npm
and npx, uv with uvx and managed Python 3.13, and the ProB version from
`install.sh`. The builder compiles fuzz at `install.sh`'s pinned revision
using GCC, Make, Bison, and Flex:

```bash
mkdir -p runtime-assets
scripts/build-handoff-runtime.sh runtime-assets /path/to/ProB
```

Publish the exact `z-spec-linux-amd64-v1.tar.gz` bytes and pin the printed
SHA-256 in `.punt-labs/ethos/checks/snapshots/z-spec.yaml`. A fresh build
may produce a different digest. After downloading the release asset,
verify and install it under the digest in the profile:

```bash
sha='digest-from-profile'
printf '%s  %s\n' "$sha" z-spec-linux-amd64-v1.tar.gz | sha256sum --check
install -D z-spec-linux-amd64-v1.tar.gz \
    "$HOME/.punt-labs/ethos/runtimes/$sha.tar.gz"
```

The snapshot copies the locked dependency caches into private scratch and
builds a fresh `.venv`; it never writes the live checkout's `.tmp` or
other scratch directories. Rebuild and repin the bundle when the locked
dependencies or required tools change.

## Project structure

Everything the Claude Code plugin ships lives under `plugin/`, and nothing
else does. The marketplace installs that one directory with Claude Code's
`git-subdir` source, so an install never fetches `src/`, `tests/`, `docs/`, or
the spec corpus.

```text
plugin/                 # THE SHIPPED SURFACE — a marketplace install gets this
  .claude-plugin/
    plugin.json         # Plugin manifest (name: z-spec-dev in working tree)
  commands/
    check.md            # /z-spec:check (prod)
    check-dev.md        # /z-spec-dev:check-dev (dev)
    b-check.md          # /z-spec:b-check (prod, B-Method)
    b-check-dev.md      # /z-spec-dev:b-check-dev (dev, B-Method)
    ...                 # One prod + one dev variant per command
  hooks/
    hooks.json          # PostToolUse registration
    suppress-output.sh  # Renders each tool result as a panel
  reference/
    z-notation.md       # Z notation cheat sheet
    schema-patterns.md  # Common patterns and ProB tips
    probcli-guide.md    # probcli command reference
    b-notation.md       # B-Method notation reference
    b-machine-patterns.md  # B machine patterns and Z-to-B translation
  templates/
    preamble.tex        # LaTeX preamble for generated specs
  tutorials/intro/      # The lesson collection the Tutorial menu entry opens
scripts/                # Not shipped: release tooling
  release-plugin.sh     # Swap to prod name + MCP command, remove -dev commands
  restore-dev-plugin.sh # Restore dev state after tagging
tools/
  gen_dev_commands.py   # Generate/verify the plugin/commands/*-dev.md twins
```

The commands cite their reference documents as `reference/<name>.md` — paths
relative to the plugin root, which is why the reference library, the
templates, and the tutorials sit inside `plugin/` rather than beside it.
`examples/` does not: it is the spec corpus `make check` type-checks and
model-checks, not plugin content.

Two rules follow from this layout, and both are load-bearing:

- **The plugin surface must not reach outside itself at runtime.** A command
  or hook may name a path under the plugin root or under the *consumer's*
  repo; it may not name a file elsewhere in this repo, because that file is
  absent from an installed plugin. `${CLAUDE_PLUGIN_ROOT}` is `plugin/`.
- **A dev session loads `--plugin-dir plugin`, not `.`**, so `CLAUDE_PLUGIN_ROOT`
  is the same directory a real install checks out (see Local test, above).

## `ZSPEC_PLUGIN_ROOT`

`plugin/.claude-plugin/plugin.json` injects `ZSPEC_PLUGIN_ROOT` into the MCP
server's environment, set to `${CLAUDE_PLUGIN_ROOT}` — the plugin checkout
that ships the tutorials, reference docs, and templates. Two call sites read
it:

- `lux/session.py`'s `_default_tutorial_manifest` resolves the shipped
  `tutorials/intro/manifest.toml` through it, falling back to
  `plugin/tutorials/intro/manifest.toml` inside a dev checkout when the env
  var is unset (the installed server runs from site-packages, where the
  source tree holds no tutorials at all).
- `lux/project.py`'s `ProjectRoot` reads it only to decide whether a warning
  is warranted: its presence means the server's cwd is the pinned plugin
  checkout, so a `CLAUDE_PROJECT_DIR` resolution failure falling back to
  `Path.cwd()` would silently name z-spec's own repo as the user's project
  instead of raising.

This solves the manifest lookup for a Claude Code plugin install. A
**standalone wheel install** (`pip install punt-z-spec` / `uv tool install`
with no Claude Code plugin) has no `plugin.json` to set the env var and falls
back to `__file__`-relative resolution, which is not guaranteed wheel-safe if
package data ever moves — tracked as bead `z-spec-9v6`, needing
`importlib.resources` packaging. This is a minority install path, not the
primary Claude Code plugin journey.

## Module map

| Module | Responsibility |
|--------|---------------|
| `__main__.py` | Typer CLI — the verb surface |
| `server.py` | FastMCP server (key: `zspec`) — the tool surface; owns the lux session lifespan |
| `logging_config.py` | `DiagnosticLog.configure` — the one place entry points configure diagnostics, through `punt-observe` |
| `usage.py` | `Usage` — the typed usage-event schemas and the per-call recorder both surfaces share |
| `server_context.py` | Shared per-request context both surfaces build commands from |
| `commands/registry.py` | The canonical capability list (`CAPABILITIES`) and each capability's name on each surface |
| `commands/*.py` | One command per capability: `check`, `test`, `animate`, `model_check`, `report`, `doctor`, `partition`, `audit`, `show`, `browse`, `picker`, `enable`, `disable` |
| `commands/enablement.py` | The one MCP tool `enable`/`disable` both route through, per punt-kit `tool-enable-disable.md` §2.14 |
| `commands/result.py` | `CommandResult` — the envelope every command returns |
| `commands/options.py` | Parameter bundles for the probcli-backed commands |
| `fuzz.py` | Wrapper for the `fuzz` type-checker |
| `prob.py` | Wrapper for the `probcli` model checker |
| `prob_output.py` | probcli output parsing shared across commands |
| `parser.py` | LaTeX Z specification parser → `SpecModel` |
| `report.py` | Report I/O — `<stem>.<type>.json` beside the `.tex` |
| `atomic_file.py` | Crash-safe file writes used by report and audit persistence |
| `coverage.py` | Spec coverage accounting |
| `gate.py` | Quality-gate composition helpers |
| `claude_md.py` | CLAUDE.md/AGENTS.md-facing helpers (enablement doc rewriting) |
| `manifest.py` | Tutorial collection manifests (`manifest.toml`) |
| `display.py` | `LuxDisplay` — the one module that publishes scenes to the lux Hub |
| `applet.py` | Builds a single spec's tabbed lux scene |
| `browser.py` | Builds a collection's tabbed scene and the spec picker |
| `picker_scene.py` | The spec-picker scene the Browse menu entry raises |
| `lux/session.py` | `ZSpecLuxSession` — the per-process menu session the lifespan owns |
| `lux/identity.py` | Per-session app identity and its menu labels (**name must be ASCII**) |
| `lux/clients.py` | REST and hub-listener clients built from one identity |
| `lux/entry.py` | `ZSpecMenuEntry`/`ZSpecMenuEntries` — the Tutorial and Browse menu entries |
| `lux/menu.py`, `lux/subscription.py`, `lux/command_ports.py`, `lux/ports.py` | Menu registration, the receive leg, and its transport protocols |
| `lux/click.py` | Click-to-command dispatch shared by both menu entries |
| `lux/project.py` | `ProjectRoot` — the user's open project for a plugin-launched server |
| `types/` | Domain types: `spec`, `fuzz`, `prob`, `partition`, `audit`, `enablement`, `reports`, `trace`, `tutorial` |

This table is refreshed by hand; when it drifts from `commands/registry.py`'s
`CAPABILITIES` tuple or the `src/punt_zspec/` tree, the registry and the tree
are authoritative.

## Diagnostics and usage telemetry

The CLI, MCP server and hook adopt the shared `punt-observe` package, pinned to a PyPI
release in `pyproject.toml`. Library modules only declare
`logger = logging.getLogger(__name__)`; nothing under `src/` configures
logging except `logging_config.py`, and
`tests/test_observability.py` bans `basicConfig` and stdlib rotating
handlers there.

| Process | Entry point | Role | Diagnostic sink | Usage capture |
|---------|-------------|------|-----------------|---------------|
| `z-spec <verb>` | `__main__.main` callback | `cli` | `~/.punt-labs/z-spec/logs/z-spec.log`; WARNING+ also to stderr | `z-spec.cli.<capability>` events, flushed when the verb exits |
| `z-spec mcp` | `__main__.main` callback, then `server.lifespan` | `mcp` | same file; WARNING+ to stderr, never stdout | `z-spec.mcp.<capability>` events for the server's lifetime |
| PostToolUse | `plugin/hooks/suppress-output.sh` delegates diagnostics to `z-spec-hook` | `hook` | same file; never stdout | None |

The hook records its own formatting outcome (`formatted`, `fallback` or
`failed`), never the tool response or a second copy of its verdict. If the
diagnostic process cannot run or write the log, the formatter warns on stderr
and still returns the formatted response.
z-spec spawns no daemon or detached worker; `fuzz` and `probcli` are child
processes whose output z-spec parses.

Each usage event carries only closed enums and a duration: `outcome`
(`ok`/`failed`/`error`), `failure` (a `CommandFailure` value) and
`duration_ms`. A new attribute or capability changes the schema in
`usage.py`; a changed meaning bumps `SCHEMA_VERSION`. The store, retention and
exporter belong to `punt-observe`; switching to OTLP export is
`TelemetryConfig` configuration, not new instrumentation.

## The OO ratchet: a good deed, not a rebaseline

`../punt-kit/standards/python.md` states the OO/coupling/suppression ratchet's
staging discipline: `make check-oo` passes only if no metric regressed on a
touched file and at least one metric improved, and `.oo-baseline.json` is
never hand-edited except via `--rebaseline` for a structural refactor. This
section adds the operational nuance the standard states tersely and this repo
has needed spelled out in practice.

**"No metric improved" means do a good deed, not a rebaseline.** When
`check-oo` reports that a change grew or churned code without paying anything
down — an unavoidable regression from, say, a genuine one-line feature
addition — the correct response is a **genuine improvement** elsewhere:
extract a god-method, split an oversized module, collapse a conditional
forest, in a touched file or in unrelated nearby debt. Find the nearest
candidate with `radon cc -s -n C -o SCORE src/punt_zspec/`. **Never** reach
for a blanket `--rebaseline` to escape the gate — `--rebaseline` for a
structural refactor is not a substitute for the paydown; even a large
feature commit must leave at least one metric genuinely better.

**Scoped rebaseline, not blanket rebaseline.** When a rebaseline is
genuinely warranted (a structural refactor that must grow some metric to
carry real feature substance), scope it: touch only the specific
`file`+`metric` entries in `.oo-baseline.json` that must grow, each with a
one-line comment justifying why the growth is unavoidable, and leave every
metric that *did* improve at its old baseline value so it still registers as
an improvement. A rebaseline that records all growth — improvements
included — and retires no debt is a blanket rebaseline, and it is the exact
negotiation this section forbids. When in doubt, ask before rebaselining.

**Never game the metric.** Do not "improve" a size or complexity score by
stripping comments, docstrings, or blank lines — that satisfies the number
while making the code harder to read, which is the opposite of what the
ratchet exists to protect.
