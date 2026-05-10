---
description: Type-check a Z specification with fuzz
argument-hint: "[file.tex]"
allowed-tools: Bash(fuzz:*), Bash(probcli:*), Bash($PROBCLI:*), Bash(which:*), Bash(pdflatex:*), Read, Glob
---

# Check Z Specification with Fuzz

Type-check a Z specification using the fuzz type-checker.

## Input

File: $ARGUMENTS

## Process

### 0. Check Prerequisites

Verify fuzz is installed:

```bash
which fuzz >/dev/null 2>&1 || echo "FUZZ_NOT_FOUND"
```

**If fuzz not found**: Stop and tell the user:
> fuzz is not installed. Run `/z-spec:setup` first to install the Z specification tools.

### 1. Ensure TeX Files Available

Before checking, ensure fuzz.sty is available in the docs/ directory:

```bash
if [ ! -f docs/fuzz.sty ]; then
    if [ -f /usr/local/share/texmf/tex/latex/fuzz.sty ]; then
        cp /usr/local/share/texmf/tex/latex/fuzz.sty docs/
        cp /usr/local/share/texmf/fonts/source/public/oxsz/*.mf docs/
    else
        curl -sL -o docs/fuzz.sty "https://raw.githubusercontent.com/Spivoxity/fuzz/master/tex/fuzz.sty"
        for mf in oxsz.mf oxsz10.mf oxsz5.mf oxsz6.mf oxsz7.mf oxsz8.mf oxsz9.mf zarrow.mf zletter.mf zsymbol.mf; do
            curl -sL -o "docs/$mf" "https://raw.githubusercontent.com/Spivoxity/fuzz/master/tex/$mf"
        done
    fi
    # Update .gitignore
    for pattern in "docs/fuzz.sty" "docs/*.mf" "docs/*.pk" "docs/*.tfm" "docs/*.aux" "docs/*.log" "docs/*.fuzz" "docs/*.toc"; do
        grep -qxF "$pattern" .gitignore 2>/dev/null || echo "$pattern" >> .gitignore
    done
fi
```

### 2. Locate the Specification

If a file path is provided, use it directly.

If no file specified:
- Look in `docs/` for `.tex` files containing Z specifications
- Present options if multiple files exist

### 3. Run Fuzz Type-Checker

```bash
fuzz -t <file>.tex
```

The `-t` flag reports types of global definitions, which helps verify the specification is correctly typed.

### 4. Interpret Results

**Success**: Fuzz outputs the types of all definitions without errors.

Example good output:
```
Given USERID
Schema Account
    balance: NN
    status: Status
End
```

**Errors**: Fuzz reports line numbers and error descriptions.

Common errors and fixes:

| Error | Likely Cause | Fix |
|-------|--------------|-----|
| `Identifier X is not declared` | Missing type definition | Add given set or free type |
| `Application of a non-function` | Using `#` incorrectly | Reformulate cardinality expression |
| `Syntax error at symbol "true"` | Using `true`/`false` | Define BOOL free type with btrue/bfalse |
| `Type mismatch` | Wrong type in expression | Check types in fuzz output |

### 5. Report Results

If successful:
- Confirm the specification type-checks
- Summarize the schemas and their types

If errors:
- List each error with line number
- Suggest specific fixes
- Offer to apply fixes

### 6. Animation Readiness Warnings

After a successful fuzz type-check, scan the specification for patterns that pass fuzz but cause probcli animation failures. For each pattern found, emit a warning. Only emit warnings that actually apply to the spec.

**Checklist** (prefix each with "Animation hint:"):

- [ ] **Unbounded `\finset` or `\pfun`**: Any `\finset X` or `X \pfun Y` where `X` is a **given set** (declared with `[X]` syntax, not a free type declared with `Type ::= ...`) and there is no `\# variable \leq maxBound` constraint in the schema predicate. Free types are already finite and do not need cardinality bounds. Fix: add an axdef constant and a cardinality constraint.

- [ ] **Cross products for records**: Any `\cross` used to combine 3+ types (e.g., `X \cross Y \cross Z`) where a named schema with fields would be more appropriate. Fix: define a schema with named fields instead.

- [ ] **Bare-type quantifiers**: Any `\forall` or `\exists` that quantifies over a given type directly (e.g., `\forall n : NAME`) instead of over a set from state (e.g., `\forall n : members`). Fix: scope the quantifier to the relevant state set.

- [ ] **Underscored free type constructors**: Any free type constructor containing `\_` (e.g., `reports\_to`). Fix: use camelCase (`reportsTo`) or concatenated names.

- [ ] **`\mu` in operation schemas**: Any use of `\mu` for record construction inside a `\Delta` or `\Xi` schema. Fix: replace with explicit set comprehension (`\{ a : Schema | ... \}`).

- [ ] **Missing operation bounds**: Any operation that **grows** a collection (adds via `\cup`, `\oplus`, `\cat` without a corresponding removal in the same operation) without a `\# collection < maxBound` precondition. Operations that replace elements (paired remove + add) do not need this guard. Fix: add a cardinality guard.

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
