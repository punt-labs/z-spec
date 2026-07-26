---
description: Type-check a Z specification with fuzz
argument-hint: "[file.tex]"
allowed-tools: mcp__plugin_z-spec_zspec__check, Read, Glob
---

# Check Z Specification with Fuzz

Type-check a Z specification using the fuzz type-checker.

## Input

File: $ARGUMENTS

## Process

### 1. Locate the Specification

If a file path is provided, use it directly.

If no file specified:

- Look in `docs/` for `.tex` files containing Z specifications
- Present options if multiple files exist

### 2. Type-check

Call `mcp__plugin_z-spec_zspec__check` with `file` set to the resolved path.

### 3. Report

The tool returns `{"ok", "errors"}`.

If the returned JSON has an `error` field (e.g. the binary is not installed),
surface `error` (and `hint` if present) verbatim to the user and stop — do not
render the normal result.

- `ok: true` → `fuzz: <name> OK`.
- `ok: false` → `fuzz: <name> FAIL`, then one line per error, indented two
  spaces: `<line>:<column>: <message>`.

The tool has written `<stem>.fuzz.json`; `/z-spec:show` (or `show_z_spec`)
will render it in the Fuzz tab.

### 4. Animation Readiness Warnings

After a successful fuzz type-check, scan the specification for patterns that pass fuzz but cause probcli animation failures. For each pattern found, emit a warning. Only emit warnings that actually apply to the spec.

**Checklist** (prefix each with "Animation hint:"):

- [ ] **Unbounded `\finset` or `\pfun`**: Any `\finset X` or `X \pfun Y` where `X` is a **given set** (declared with `[X]` syntax, not a free type declared with `Type ::= ...`) and there is no cardinality bound — either a direct `\# variable \leq maxBound` constraint or a domain subset constraint like `\dom variable \subseteq boundedSet` where `boundedSet` itself has a cardinality bound. Free types are already finite and do not need cardinality bounds. Fix: add an axdef constant and a cardinality constraint, or constrain the domain to a bounded set.

- [ ] **Cross products for records**: Any `\cross` used to combine 3+ types (e.g., `X \cross Y \cross Z`) where a named schema with fields would be more appropriate. Fix: define a schema with named fields instead.

- [ ] **Bare-type quantifiers**: Any `\forall` or `\exists` that quantifies over a given type directly (e.g., `\forall n : NAME`) instead of over a set from state (e.g., `\forall n : members`). Fix: scope the quantifier to the relevant state set.

- [ ] **Underscored free type constructors**: Any free type constructor containing `\_` (e.g., `reports\_to`). Fix: use camelCase (`reportsTo`) or concatenated names.

- [ ] **`\mu` in operation schemas**: Any use of `\mu` for record construction inside a `\Delta` or `\Xi` schema. Fix: replace with explicit set comprehension (`\{ a : Schema | ... \}`).

- [ ] **Missing operation bounds**: Any operation that **grows** a collection (adds via `\cup` or `\cat` without a corresponding removal in the same operation) without a `\# collection < maxBound` precondition. Operations that replace elements (paired remove + add) do not need this guard. Operations that grow a `\pfun` whose domain is constrained to a bounded set (e.g., `\dom handles \subseteq members` where `\# members \leq maxMembers`) are transitively bounded and do not need a separate guard. Note: `\oplus` (functional override) updates existing mappings and does not need a bounds guard unless it introduces new domain elements. Fix: add a cardinality guard.

**Output format**:

```
Animation hint: members (\finset NAME) has no cardinality bound.
  Add: \# members \leq maxMembers (with maxMembers in axdef)

Animation hint: assignments uses \cross triple — consider a named schema.
  Replace: \finset (NAME \cross HANDLE \cross Relation)
  With:    \finset Assignment (define Assignment schema with fields)

Animation hint: \forall n : NAME quantifies over bare given type.
  Replace: \forall n : NAME @ ...
  With:    \forall n : members @ ...
```

## Reference

- Z notation: `reference/z-notation.md`
- Schema patterns: `reference/schema-patterns.md`
