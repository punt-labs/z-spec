---
root: false
targets: ["claudecode"]
description: "Claude Code MCP tools and vendored tool guides (ethos, vox, beadle, z-spec plugin)"
globs: []
---

# Claude Code tool guides

Claude Code drives several MCP servers in this repo; each has its own
vendored guide, loaded on demand rather than inlined here:

- [`.punt-labs/z-spec/CLAUDE.md`](../.punt-labs/z-spec/CLAUDE.md) — the
  `zspec` MCP server and the z-spec plugin (enablement, check/test/partition/
  audit/code2model/model2code, lux display).
- [`.punt-labs/vox/CLAUDE.md`](../.punt-labs/vox/CLAUDE.md) — the `mic` MCP
  server (text-to-speech, vibe, music, recordings).
- [`.punt-labs/beadle/CLAUDE.md`](../.punt-labs/beadle/CLAUDE.md) — the
  `email` MCP server (agent mailbox, trust model).

## Ethos and delegation

Identity: `agent: claude` per `.punt-labs/ethos.yaml`. This repo does **not**
mount the `punt-labs/team` submodule — z-spec is a marketplace plugin, and
`claude plugin install` clones with submodules, so an SSH `.gitmodules` URL
breaks installs for users without a GitHub key. `.punt-labs/ethos.yaml`
(tracked) plus the global `~/.punt-labs/ethos/` stand in for it instead.
Vendor an individual file here only if it is z-spec's own; never the roster.

The COO does not write code. The only files the leader edits directly:
`CHANGELOG.md`, `CLAUDE.md`, `README.md`, `TESTING.md`, `docs/WORKFLOW.md`,
design docs, and plan files — and must not read implementation files before
writing a design spec, so a predetermined write-set never leaks into the
specialist's extraction or restructuring choices.

## Specialist pairings

z-spec's specialists are Z's foundational authors, with Python/CLI/lux
specialists beneath them. Worker and evaluator are always distinct; Claude
is the leader, never the evaluator.

| Task type | Worker | Evaluator |
|-----------|--------|-----------|
| Z schema authoring / notation choices | `jms` (Spivey) | `jra` (Abrial) |
| Refinement / B-method / proof obligations | `jra` | `jms` |
| Typing rules / fuzz semantics | `jms` | `jra` |
| ProB-compatibility constraints | `jra` | `jms` |
| Skill prompts (`plugin/commands/`) | `jms` | `adt` (Hopper) |
| Python: parsing, wrappers, report I/O, commands | `rmh` (Hettinger) | `gvr` (van Rossum) |
| MCP tool surface (`server.py`) | `rmh` | `mdm` (Pike) |
| CLI surface (`__main__.py`) | `mdm` | `rmh` |
| Lux rendering (`applet.py`, `browser.py`, `display.py`) | `edt` (Tufte) | `dna` (Norman) |
| Lux receive leg (`lux/` session, menu, subscription) | `rmh` | `edt` |
| Plugin packaging / dev-prod swap / marketplace | `mdm` | `adb` (Lovelace) |
| Quarry `z-specification` collection / sync | `adb` | `rmh` |
| Test infrastructure and fixtures | `rmh` | `gvr` |

Use the `formal` pipeline for any spec change (fuzz + probcli + report),
`standard` for Python/skill-prompt changes, `quick` only for typo fixes that
never touch a schema. Review-cycle fix rounds (Copilot/Bugbot findings) use a
bare `Agent()`, not a mission.

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
