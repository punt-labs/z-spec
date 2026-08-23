# Development

This document covers contributor-facing details: how to run the dev plugin
against the working tree, how a release swaps between dev and prod plugin
names, and how the plugin directory is laid out. Most of this only matters if
you are editing z-spec itself.

For quality-gate commands, see the [Development section of the README](../README.md#development).

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
it), and it strips the `-dev` command twins. `restore-dev-plugin.sh` restores
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
