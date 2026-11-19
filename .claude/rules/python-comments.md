---
paths:
  - "**/*.py"
---

# Comments & Docstrings

**Updated:** 2026-11-18

Canonical sources: [Agent Engineering §8](https://github.com/punt-labs/punt-kit/blob/main/standards/agent-engineering.md#8-write-for-the-next-reader)
and [Python Standards](https://github.com/punt-labs/punt-kit/blob/main/standards/python.md#docstrings-and-api-reference).

## PY-DOC-1: Comments explain *why*, not *what*

The code shows what. Comment only a non-obvious reason, invariant, or constraint
that the next reader needs. Remove redundant prose and commented-out code.

## PY-DOC-2: Comments and docstrings never narrate the development process

Do not cite issue trackers (IDs or links), beads, PRs, review findings,
development phases, or plans. Do not narrate edits or past implementations
("now uses X", "used to do X, now does Y"). Keep that history in commits, PRs,
the issue tracker, or the changelog.

Remove non-compliant comments and docstring prose whenever you notice them,
even when you did not write them. Preserve any useful current rationale,
invariant, or contract by rewriting it. Update or remove any prose your
change makes false in the same patch.

## PY-DOC-3: Document the public API in Google style

Require docstrings on public modules, packages, classes, functions, and
methods in `src/`, not on private names or tests. Start with an imperative
summary per [PEP 257](https://peps.python.org/pep-0257/). Add sections only
when they convey information the caller needs:

- `Args:` describes only parameters whose names leave something unclear,
  such as units, allowed values, or the meaning of a sentinel.
- `Returns:` or `Yields:` explains non-obvious result semantics. Keep parameter
  and result types in annotations, not in docstrings.
- `Raises:` lists every exception callers can be expected to handle and when
  it escapes, including errors propagated from callees. Omit an empty section.

Every registered MCP tool needs a docstring, even if its implementation has a
private name. Models can read these docstrings at runtime, so give them a
fuller contract: when to use the tool, how to supply inputs, what the result
means, and when to expect errors. Keep the contract accurate without
duplicating type annotations or narrating edits.
