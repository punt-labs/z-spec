# Agent Instructions

This is a Claude Code plugin for formal Z specifications. The plugin uses skill prompts to guide spec creation, type-checking (fuzz), and animation (probcli). No application code — the tools are external binaries.

This project follows [Punt Labs standards](https://github.com/punt-labs/punt-kit).

## Quality Gates

```bash
npx markdownlint-cli2 "**/*.md" "#node_modules"
```

All markdown must pass markdownlint before commit. CI enforces this via `docs.yml`.

## What NOT to Change Without Care

- **`skills/z-spec/SKILL.md`** — the main skill prompt. Test by running `/z check` and `/z test` after any edit.
- **Z notation conventions** — the plugin outputs ProB-compatible Z (avoids B keyword conflicts, uses bounded integers, flat schemas). These constraints are intentional.

## Standards References

- [GitHub](https://github.com/punt-labs/punt-kit/blob/main/standards/github.md)
- [Workflow](https://github.com/punt-labs/punt-kit/blob/main/standards/workflow.md)
- [Plugins](https://github.com/punt-labs/punt-kit/blob/main/standards/plugins.md)
