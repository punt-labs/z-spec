---
paths:
  - '**/*.py'
---
# Python standards

z-spec follows Punt Labs' org-wide Python standard in full: 22 scoped rule
files (`python-*.md`, one per concern — style, typing, OO ratchet, coupling,
suppression policy, and more) that load automatically by path in any repo
checked out inside the `punt-labs/` workspace meta-repo, from
`../.claude/rules/python-*.md` (ancestor-directory walk, scoped via each
file's own `paths:` frontmatter).

**This rule intentionally does not inline those 22 files.** Per
`punt-kit/standards/context-mgmt.md`, DRY means de-duplicating a single
source of truth, not deleting the reference and hoping the reader already
knows the content — so this file names the dependency explicitly instead of
either copying it stale or silently omitting it.

**Standalone-clone caveat, stated honestly:** if z-spec is checked out on its
own (not as a sibling inside `punt-labs/`), `../.claude/rules/python-*.md`
does not exist and this pointer resolves to nothing. In that case:

- Fetch the canonical set from
  [`punt-kit/standards/python.md`](https://github.com/punt-labs/punt-kit/blob/main/standards/python.md),
  the summary doc that indexes all 22 rule files, or
- Check out inside the `punt-labs/` workspace meta-repo per this repo's own
  `CLAUDE.md`, which is the supported layout and the one CI and every other
  Punt Labs Python repo assumes.

Do not re-derive Python style rules from memory or from a different
project's conventions — the 22-file standard is the one source of truth,
wherever it is reached from.

**Scoping caveat, stated honestly:** the file-selection pattern above
(`**/*.py`) is enforced only for `claudecode`, which reads this file from
`.claude/rules/python-standards-pointer.md` with a `paths:` frontmatter
Claude Code checks per-file. `codexcli` and `pi`
have no modular rules directory to scope against — rulesync folds this
rule's body unconditionally into the shared root `AGENTS.md`, so those two
tools see this Python pointer on every file, not only `**/*.py` (a pointer,
not a style rule itself, so the practical cost is a stale reference visible
outside Python work rather than a misapplied convention). `opencode` is
intentionally left out of `targets` above: its `instructions` array is
project-wide with no glob support either, and rulesync would additionally
register this rule a second time (root `AGENTS.md` plus
`.opencode/memories/python-standards-pointer.md`) since opencode reads both
— a real double-load, not just an unscoped one. Getting the guidance into
AGENTS.md via `codexcli`/`pi` already covers opencode's users; excluding it
from `targets` avoids the duplicate registration without losing coverage.
