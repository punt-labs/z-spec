---
root: false
targets: ["claudecode", "codexcli", "pi"]
description: "Z notation conventions (ProB-compatible) — do not \"modernize\""
globs: ["**/*.tex", "examples/**"]
---

# Z conventions (ProB-compatible) — do not "modernize"

- `\quad~` for continuation lines inside `\begin{zed}`; fuzz has no `\t1`.
- `ZBOOL ::= ztrue | zfalse`, not a native Bool.
- Two-letter lowercase free-type prefixes to avoid B keyword conflicts.
- Flat schemas; bounded integers so ProB can animate.

**Scoping caveat, stated honestly:** the file-selection patterns above
(`**/*.tex`, `examples/**`) are enforced only for `claudecode`, which reads
this file from `.claude/rules/z-conventions.md` with a `paths:` frontmatter
Claude Code checks per-file. `codexcli` and `pi`
have no modular rules directory to scope against — rulesync folds this rule's
body unconditionally into the shared root `AGENTS.md`, so those two tools
apply these Z conventions to every file, not only `.tex` specs and
`examples/**`. `opencode` is intentionally left out of `targets` above:
its `instructions` array is project-wide with no glob support either, and
rulesync would additionally register this rule a second time (root
`AGENTS.md` plus `.opencode/memories/z-conventions.md`) since opencode reads
both — a real double-load, not just an unscoped one. Getting the guidance
into AGENTS.md via `codexcli`/`pi` already covers opencode's users; excluding
it from `targets` avoids the duplicate registration without losing coverage.
