---
description: Type-check a B machine with probcli
argument-hint: "[machine.mch]"
allowed-tools: Bash(probcli:*), Bash($PROBCLI:*), Bash(which:*), Read, Glob
---

# Check B Machine with probcli

Type-check a B machine (`.mch`, `.ref`, or `.imp`) using probcli.

## Input

File: $ARGUMENTS

## Process

### 0. Check Prerequisites

Verify probcli is installed:

```bash
PROBCLI="${PROBCLI:-$HOME/Applications/ProB/probcli}"
if ! which probcli >/dev/null 2>&1 && [ ! -x "$PROBCLI" ]; then
    echo "PROBCLI_NOT_FOUND"
fi
```

**If probcli not found**: Stop and tell the user:
> probcli is not installed. Run `/z-spec:setup probcli` first.

### 1. Locate the Machine

If a file path is provided, use it directly.

If no file specified:

- Look in `specs/` for `.mch`, `.ref`, or `.imp` files
- Present options if multiple files exist

### 2. Run probcli Type-Check

```bash
probcli <file>
```

probcli parses the machine, checks types, and reports errors. Unlike Z specifications
(which use fuzz for type-checking), B machines use probcli for both type-checking and animation.

### 3. Interpret Results

**Success**: probcli exits with code 0, no error output.

**Errors**: probcli reports syntax errors, type errors, and well-formedness violations.

Common errors and fixes:

| Error | Likely Cause | Fix |
|-------|--------------|-----|
| `Syntax Error` | Invalid B syntax | Check clause order (SETS before VARIABLES before INVARIANT) |
| `Type Error` | Mismatched types in predicate | Verify variable types in INVARIANT match OPERATIONS usage |
| `Identifier not found` | Undefined variable or constant | Add to VARIABLES or CONSTANTS clause |
| `Parse error: expecting END` | Missing END keyword | Each PRE/IF/SELECT needs a matching END |
| `Not a B file` | Wrong file extension | Use `.mch`, `.ref`, or `.imp` |
| `PROPERTIES missing` | CONSTANTS without PROPERTIES | Add PROPERTIES clause with typing constraints |

### 4. Report Results

If successful:

- Confirm the machine type-checks
- List the machine's SETS, VARIABLES, and OPERATIONS

If errors:

- List each error with location
- Suggest specific fixes
- Offer to apply fixes

## Reference

- B notation: `reference/b-notation.md`
- B machine patterns: `reference/b-machine-patterns.md`
- probcli options: `reference/probcli-guide.md`
