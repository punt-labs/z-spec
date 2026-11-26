# Claude Code tool guides

Claude Code drives several MCP servers in this repo; each has its own
vendored guide, loaded on demand rather than inlined here:

- [`.punt-labs/z-spec/CLAUDE.md`](../../.punt-labs/z-spec/CLAUDE.md) — the
  `zspec` MCP server and the z-spec plugin (enablement, check/test/partition/
  audit/code2model/model2code, lux display).
- [`.punt-labs/vox/CLAUDE.md`](../../.punt-labs/vox/CLAUDE.md) — the `mic` MCP
  server (text-to-speech, vibe, music, recordings).
- [`.punt-labs/beadle/CLAUDE.md`](../../.punt-labs/beadle/CLAUDE.md) — the
  `email` MCP server (agent mailbox, trust model).

## Z reference materials (Quarry)

The `z-specification` Quarry collection is the authoritative Z reference
library (the Z textbook, the fuzz manual, Bowen's formal specs guide, course
notes). Search it with `mcp__quarry__search_documents` (`collection:
"z-specification"`) before writing schemas or answering Z notation
questions — training-data Z is unreliable.

## Release

`punt-z-spec` publishes to PyPI; the plugin ships to the marketplace with
dev/prod namespace isolation (`plugin.json` carries `"name": "z-spec-dev"`
in the working tree). `scripts/release-plugin.sh` swaps the name for a tag;
`scripts/restore-dev-plugin.sh` restores dev state after. Every prod slash
command has a generated `-dev` twin (`make gen-dev-commands`,
`make check-dev-commands` gates drift).
