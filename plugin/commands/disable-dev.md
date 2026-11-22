---
description: Turn z-spec off in this repository
allowed-tools: mcp__plugin_z-spec-dev_zspec__enablement, Read
---

# Disable z-spec here

Stop z-spec composing into this repository: its MCP tools decline and it
registers no lux menu entries. Nothing it deposited is deleted.

## Process

Call `mcp__plugin_z-spec-dev_zspec__enablement` with `action: "disable"`. It returns
`{ok, action, enabled, root, marker, guide, import_line}`.

The call is idempotent — disabling a repository that was never enabled is a
no-op. It never runs git.

## What it changes

| Path | What happens |
|------|--------------|
| `CLAUDE.md` | The `@.punt-labs/z-spec/CLAUDE.md` line is removed |
| `.punt-labs/z-spec/enabled` | Deleted |
| `.punt-labs/z-spec/` | Left in place, dormant — never deleted |

## Output

The three paths are where the marker, the guide, and the import line were —
the marker and the line are gone, the guide is dormant. This is what
`z-spec disable` prints, and the tool returns the same values:

```
z-spec disabled in /repo
  marker: /repo/.punt-labs/z-spec/enabled
  guide:  /repo/.punt-labs/z-spec/CLAUDE.md
  import: @.punt-labs/z-spec/CLAUDE.md
Commit its removal so the repo stays off for everyone.
```

If `ok` is false, either you are outside a git working tree or the repository
refused the write. Report the error verbatim.

## Notes

- Disabling does not touch the `z-spec` CLI, which is never gated.
- To turn it back on, run `/z-spec-dev:enable-dev`.
