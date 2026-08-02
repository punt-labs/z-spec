# z-spec (formal Z specifications)

z-spec type-checks Z specifications with fuzz, model-checks and animates them
with ProB, and renders them in lux. This doc is how an *agent* drives z-spec in
this repo — not how to develop z-spec itself.

z-spec is per-repo: its MCP tools and its lux menu entries are live only where
someone ran `z-spec enable` and committed `.punt-labs/z-spec/enabled`. In a repo
with no marker every MCP tool except `enablement` declines with a one-line
message naming the enable command, and z-spec contributes no lux menu entries.
The `z-spec` CLI is never gated — a shell invocation is deliberate by
definition.

## Enabling z-spec in a repo

- `/z-spec:enable` (or `z-spec enable`) — turn z-spec on here: deposit this
  guide, write the marker, add the `@`-import line to the repo `CLAUDE.md`.
  Idempotent; re-running is also the upgrade path.
- `/z-spec:disable` (or `z-spec disable`) — turn it off: prune the import line
  and delete the marker. The `.punt-labs/z-spec/` subtree is left dormant, never
  deleted.

Neither surface runs git. The marker is a tracked file: commit it in a PR so
enablement is reviewed and identical for everyone who clones.

## Working with a specification

| Command | What it does |
|---------|--------------|
| `/z-spec:check [file]` | Type-check with fuzz |
| `/z-spec:test [file]` | Animate and model-check with ProB, save the report |
| `/z-spec:partition [spec]` | Derive test cases with TTF testing tactics |
| `/z-spec:audit [spec]` | Audit test coverage against the spec's constraints |
| `/z-spec:code2model [focus]` | Write a Z spec from a codebase or description |
| `/z-spec:model2code [spec]` | Generate code and tests from a spec |
| `/z-spec:doctor` | Report toolchain health (fuzz, probcli, fuzz.sty) |
| `/z-spec:help` | The full command list |

Type-check before you model-check: fuzz catches the type errors that make ProB's
output unreadable. Every command works on `.tex` files carrying `zed`,
`schema`, and `axdef` environments.

## Display

`show_z_spec` renders a spec and its reports as tabs in lux; `pick` discovers
the `.tex` specs under a directory and renders one tab each; `browse` opens a
tutorial manifest. The lux right-click menu carries the same two entries
(Tutorial, Browse) — but only in a repo where z-spec is enabled.

## Gotchas

- A repo with no `enabled` marker is a graceful no-op, not an error. z-spec
  never turns itself on as a side effect of first use.
- Reinstalling the CLI does not restart a running MCP server. Reconnect the
  z-spec server after `make install` or the old code keeps answering.
- ProB rejects B keywords and unbounded integers. Keep specs flat, bound the
  integer ranges, and prefix free types so they cannot collide.
