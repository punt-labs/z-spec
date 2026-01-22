---
description: Type-check a Z specification with fuzz
argument-hint: "[file.tex]"
allowed-tools: Bash(fuzz:*), Read, Glob
---

# Check Z Specification with Fuzz

Type-check a Z specification using the fuzz type-checker.

## Input

File: $ARGUMENTS

## Process

### 0. Ensure TeX Files Available

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

### 1. Locate the Specification

If a file path is provided, use it directly.

If no file specified:
- Look in `docs/` for `.tex` files containing Z specifications
- Present options if multiple files exist

### 2. Run Fuzz Type-Checker

```bash
fuzz -t <file>.tex
```

The `-t` flag reports types of global definitions, which helps verify the specification is correctly typed.

### 3. Interpret Results

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

### 4. Report Results

If successful:
- Confirm the specification type-checks
- Summarize the schemas and their types

If errors:
- List each error with line number
- Suggest specific fixes
- Offer to apply fixes

## Reference

- Z notation: `reference/z-notation.md`
- Schema patterns: `reference/schema-patterns.md`
