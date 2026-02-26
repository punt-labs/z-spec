# Agent Instructions

This is a Claude Code plugin for formal Z specifications. The plugin uses skill prompts to guide spec creation, type-checking (fuzz), and animation (probcli). No application code — the tools are external binaries.

This project follows [Punt Labs standards](https://github.com/punt-labs/punt-kit).

## Quality Gates

```bash
npx markdownlint-cli2 "**/*.md" "#node_modules"
```

All markdown must pass markdownlint before commit. CI enforces this via `docs.yml`.

## Z Reference Materials (Quarry)

The **`z-specification`** Quarry collection contains the authoritative Z notation reference library: the Z textbook (`zedbook.pdf`), fuzz type-checker manual (`fuzzman.pdf`), Bowen's formal specs guide, lecture slides (00–12), semantics slides (00–07), exercises, solutions, and course notes. This collection is sourced from `/Users/jfreeman/Coding/task-mgmt-system/docs` and registered for incremental sync.

**You must use Quarry (`mcp__quarry__search_documents` with `collection: "z-specification"`) to ground your Z work in these materials.** Before writing schemas, choosing conventions, or answering questions about Z notation, search this collection first. Do not rely on training data alone — these documents define the correct notation, typing rules, and idioms for this project.

## What NOT to Change Without Care

- **`skills/z-spec/SKILL.md`** — the main skill prompt. Test by running `/z check` and `/z test` after any edit.
- **Z notation conventions** — the plugin outputs ProB-compatible Z (avoids B keyword conflicts, uses bounded integers, flat schemas). These constraints are intentional.

## Issue Tracking

This project uses **beads** (`bd`) for issue tracking. If an issue discovered here affects multiple repos or requires a standards change, escalate to a [punt-kit bead](https://github.com/punt-labs/punt-kit) instead (see [bead placement scheme](../CLAUDE.md#where-to-create-a-bead)).

## Standards References

- [GitHub](https://github.com/punt-labs/punt-kit/blob/main/standards/github.md)
- [Workflow](https://github.com/punt-labs/punt-kit/blob/main/standards/workflow.md)
- [Plugins](https://github.com/punt-labs/punt-kit/blob/main/standards/plugins.md)
