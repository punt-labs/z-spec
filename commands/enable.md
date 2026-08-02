---
description: Turn z-spec on in this repository
allowed-tools: mcp__plugin_z-spec_zspec__enablement, Read
---

# Enable z-spec here

z-spec is per-repo. Its MCP tools and its lux menu entries are live only where
someone ran enable and committed `.punt-labs/z-spec/enabled`. Run this once per
repository that does formal Z work.

## Process

Call `mcp__plugin_z-spec_zspec__enablement` with `action: "enable"`. It returns
`{ok, action, enabled, root, marker, guide, import_line}`.

The call is idempotent, and re-running it is the upgrade path — it redeposits
the shipped guide, adds the `@`-import line only if absent, and rewrites the
marker. It never runs git.

## What it writes

| Path | Why |
|------|-----|
| `.punt-labs/z-spec/CLAUDE.md` | The z-spec agent guide, overwritten wholesale |
| `.punt-labs/z-spec/enabled` | The marker every z-spec MCP tool reads |
| `CLAUDE.md` | One bare line: `@.punt-labs/z-spec/CLAUDE.md` |

## Output

Report the three paths, then the one action left for the human. This is what
`z-spec enable` prints, and the tool returns the same values:

```
z-spec enabled in /repo
  marker: /repo/.punt-labs/z-spec/enabled
  guide:  /repo/.punt-labs/z-spec/CLAUDE.md
  import: @.punt-labs/z-spec/CLAUDE.md
Commit the marker so enablement travels with the repo.
```

If `ok` is false, either you are outside a git working tree or the repository
refused the write. Report the error verbatim; do not create a repository.

## Notes

- The `z-spec` CLI is never gated. `z-spec check` and friends work from a
  terminal whether or not the marker exists.
- To turn it off again, run `/z-spec:disable`.
