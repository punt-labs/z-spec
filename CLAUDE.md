# Agent Instructions

This is a Claude Code plugin for formal Z specifications. The plugin uses skill prompts to guide spec creation, type-checking (fuzz), and animation (probcli). No application code — the tools are external binaries.

This project follows [Punt Labs standards](https://github.com/punt-labs/punt-kit).

## Scratch Files

Use `.tmp/` at the project root for scratch and temporary files — never `/tmp`. The `TMPDIR` environment variable is set via `.envrc` so that `tempfile` and subprocesses automatically use it. Contents are gitignored; only `.gitkeep` is tracked.

## Quality Gates

```bash
npx markdownlint-cli2 "**/*.md" "#node_modules"
```

All markdown must pass markdownlint before commit. CI enforces this via `docs.yml`.

## Z Reference Materials (Quarry)

The **`z-specification`** Quarry collection contains the authoritative Z notation reference library: the Z textbook (`zedbook.pdf`), fuzz type-checker manual (`fuzzman.pdf`), Bowen's formal specs guide, lecture slides (00–12), semantics slides (00–07), exercises, solutions, and course notes. This collection is sourced from the Z textbook collection and registered for incremental sync.

**You must use Quarry (`mcp__quarry__search_documents` with `collection: "z-specification"`) to ground your Z work in these materials.** Before writing schemas, choosing conventions, or answering questions about Z notation, search this collection first. Do not rely on training data alone — these documents define the correct notation, typing rules, and idioms for this project.

## What NOT to Change Without Care

- **`skills/z-spec/SKILL.md`** — the main skill prompt. Test by running `/z-spec:check` and `/z-spec:test` after any edit.
- **Z notation conventions** — the plugin outputs ProB-compatible Z (avoids B keyword conflicts, uses bounded integers, flat schemas). These constraints are intentional.

## Documentation Discipline

### CHANGELOG

Entries are written in the PR branch, before merge — not retroactively on main. If a PR changes user-facing behavior and the diff does not include a CHANGELOG entry, the PR is not ready to merge. Follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format under `## [Unreleased]`.

### README

Update README.md when user-facing behavior changes (new flags, commands, defaults, config, spec conventions).

### PR/FAQ

Update prfaq.tex when the change shifts product direction or validates/invalidates a risk assumption.

## Pre-PR Checklist

- [ ] **CHANGELOG entry** included in the PR diff under `## [Unreleased]` ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format)
- [ ] **README updated** if user-facing behavior changed (new flags, commands, defaults, config, spec conventions)
- [ ] **PR/FAQ updated** if the change shifts product direction or validates/invalidates a risk assumption
- [ ] **Quality gates pass** — `npx markdownlint-cli2 "**/*.md" "#node_modules"`

### Code Review Flow

Do **not** merge immediately after creating a PR. Expect **2–6 review cycles** before merging.

1. **Create PR** — push branch, open PR via `mcp__github__create_pull_request`. Prefer MCP GitHub tools over `gh` CLI.
2. **Request Copilot review** — use `mcp__github__request_copilot_review`.
3. **Watch for feedback in the background** — `gh pr checks <number> --watch` in a background task or separate session. Do not stop waiting. Copilot and Bugbot may take 1–3 minutes after CI completes.
4. **Read all feedback** via MCP: `mcp__github__pull_request_read` with `get_reviews` and `get_review_comments`.
5. **Take every comment seriously.** Do not dismiss feedback as "unrelated to the change" or "pre-existing." If you disagree, explain why in a reply.
6. **Fix and re-push** — commit fixes, push, re-run quality gates.
7. **Repeat steps 3–6** until the latest review is **uneventful** — zero new comments, all checks green.
8. **Merge only when the last review was clean** — use `mcp__github__merge_pull_request` (not `gh pr merge`).

## Issue Tracking

This project uses **beads** (`bd`) for issue tracking. If an issue discovered here affects multiple repos or requires a standards change, escalate to a [punt-kit bead](https://github.com/punt-labs/punt-kit) instead (see [bead placement scheme](../CLAUDE.md#where-to-create-a-bead)).

## Standards References

- [GitHub](https://github.com/punt-labs/punt-kit/blob/main/standards/github.md)
- [Workflow](https://github.com/punt-labs/punt-kit/blob/main/standards/workflow.md)
- [Plugins](https://github.com/punt-labs/punt-kit/blob/main/standards/plugins.md)
