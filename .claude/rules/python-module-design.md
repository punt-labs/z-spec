---
paths:
  - "**/*.py"
---

# Module and Package Design Standards

## PL-MD-1: Layering Violations

**Statement**: The dependency arrow always points inward. Core/domain
modules must never import from presentation modules (CLI, MCP server,
hooks). Types and protocols must be importable without pulling in heavy
dependencies. Violating this creates circular dependencies and makes
the core untestable without the full stack.

**Layers** (inner → outer):
1. Types/Protocols — importable with zero heavy dependencies
2. Core/Domain — business logic, data access
3. Commands — orchestration (optional layer)
4. Presentation — CLI, MCP server, hooks, applets

A module in layer N may import from layers 1..N-1, never from N+1.

**Criterion**:
- Pass: zero imports from an outer layer into an inner layer
- Fail: core module imports from CLI, server, or hook module

**Tooling**:
- `tools/oo_coupling.py` — inspect efferent coupling targets
- Grep: `grep -rn "from.*cli import\|from.*server import\|from.*hooks import" src/*/core*`
- LLM review: audit import headers of core modules

## PL-MD-2: Package Cohesion

**Statement**: A package (directory with `__init__.py`) is a unit of
organization. Its modules should collaborate — if no module in the
package imports from any sibling, the package is just a directory, not
a cohesive unit. Conversely, if every module imports every other, the
package is a tangle that should be decomposed.

**Criterion**:
- Pass: package cohesion >= 0.5 (at least half the modules import a sibling)
- Flag: package density > 0.5 (too interconnected — consider splitting)
- Fail: package cohesion == 0.0 for a package with 3+ modules

**Tooling**:
- `tools/oo_coupling.py` — `pkg_cohesion` and `pkg_intra_density` metrics
- LLM review: packages with zero cohesion that have 3+ modules

## PL-MD-3: Package Interface Width

**Statement**: A package's `__init__.py` defines its public contract.
Re-exporting too many names makes the package interface brittle — every
re-exported name is a promise to consumers. Prefer narrow package
interfaces where consumers import from submodules when they need
specific internals.

**Criterion**:
- Pass: package `__init__.py` exposes <= 20 names
- Flag: package exposes > 30 names (review whether consumers should
  import from submodules instead)

**Tooling**:
- `tools/oo_coupling.py` — `pkg_interface_width` metric
- LLM review: `__init__.py` files with large re-export lists

## PL-MD-4: Package External Dependencies

**Statement**: A package should depend on a bounded number of sibling
packages. High external coupling means the package cannot be understood,
tested, or extracted without its siblings.

**Criterion**:
- Pass: package imports from <= 5 sibling packages
- Flag: package imports from > 7 sibling packages

**Tooling**:
- `tools/oo_coupling.py` — `pkg_efferent_coupling` metric

## PL-MD-5: No Orphan Modules

**Statement**: Every module in a package should be reachable from the
package's `__init__.py` through some chain of imports. A module that
exists in a package but is never imported by any sibling or the
`__init__` is dead code or belongs in a different package.

**Criterion**:
- Pass: every module in the package is imported by at least one sibling
  or by `__init__.py`
- Fail: module exists in the package but has zero importers within
  the package

**Tooling**:
- LLM review: cross-reference `oo_coupling.py --threshold` output with
  the package module list
- Future: orphan detection in `oo_coupling.py`
