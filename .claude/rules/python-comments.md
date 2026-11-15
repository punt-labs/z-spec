---
paths:
  - "**/*.py"
---

# Comments & Docstrings

Canonical source: `punt-kit/standards/agent-engineering.md` §8 ("Write for the
next reader"). This rule enforces that standard at write time.

## PY-DOC-1: Comments explain *why*, not *what*

The code shows what; a comment that restates the code is noise. Comment the
non-obvious *why* — an invariant, a contract, a gotcha, the reason a surprising
line exists. Follow PEP 257 for docstrings (imperative mood, one-line summary
when it fits).

## PY-DOC-2: Comments and docstrings never narrate the development process

No references to development phases, plans or roadmaps, issue or bead IDs,
review-finding labels, or PR numbers in code. Those belong in commits, PRs, and
the issue tracker — not in code that outlives them. A docstring that pins the
code to a phase or a ticket documents the project, not the code, and rots the
moment that phase or ticket is forgotten.

Rewrite in place: strike the citation, keep the substance. A docstring that
names a phase or ticket becomes one that captures the non-obvious *why* — the
rationale, contract, or invariant (per PY-DOC-1) — with no reference that rots.
