---
description: Validate and animate a Z specification with probcli
argument-hint: "[file.tex] [options: -v verbose, -a N animate steps, -s N setsize]"
allowed-tools: Bash(probcli:*), Bash($PROBCLI:*), Bash(fuzz:*), Bash(which:*), Bash(pdflatex:*), Read, Glob
---

# Test Z Specification with ProB

Validate and animate a Z specification using probcli (ProB command line interface).

## Input

Arguments: $ARGUMENTS

Parse arguments:
- First positional argument: file path (or search in `docs/`)
- `-v` or `--verbose`: Show full probcli output
- `-a N` or `--animate N`: Animation steps (default: 20)
- `-s N` or `--setsize N`: Default set size for model checking (default: 2)

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
> probcli is not installed. Run `/z setup` first to install the Z specification tools.

### 1. Ensure TeX Files Available

Before testing, ensure fuzz.sty is available in the docs/ directory:

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

### 2. Locate probcli

Check for probcli:
```bash
# Check common locations
PROBCLI="${PROBCLI:-$HOME/Applications/ProB/probcli}"
if [[ ! -x "$PROBCLI" ]]; then
    which probcli || echo "probcli not found"
fi
```

If not found, inform user how to install ProB.

### 3. Locate the Specification

If a file path is provided, use it directly.
If no file specified, look in `docs/` for `.tex` files.

### 4. Run Validation Checks

Execute these checks in sequence:

#### Check 1: Parse and Initialize

```bash
probcli <file>.tex -init
```

Verifies the specification parses and has valid initial state(s).

Look for:
- `Z operation:` lines listing available operations
- `% given_set(...)` lines showing given sets
- Error messages indicating parse failures

#### Check 2: Animation

```bash
probcli <file>.tex -animate 20
```

Randomly executes operations to verify they're executable.

Look for:
- `ALL OPERATIONS COVERED` - all operations were executed
- Partial coverage indicates some operations may have unsatisfiable preconditions

#### Check 3: Constraint-Based Assertion Check

```bash
probcli <file>.tex -cbc_assertions
```

Checks if any operation can violate assertions.

Look for:
- `No counter-example to ASSERTION exists` - pass
- `No ASSERTION to check` - no assertions defined
- Counter-example found - potential assertion violation

#### Check 4: Constraint-Based Deadlock Check

```bash
probcli <file>.tex -cbc_deadlock
```

Checks for potential deadlock states.

Look for:
- `No deadlock possible` - proven deadlock-free
- Deadlock counter-example - may be unreachable (verify with model check)

#### Check 5: Model Checking

```bash
probcli <file>.tex -model_check \
    -p DEFAULT_SETSIZE 2 \
    -p MAX_INITIALISATIONS 100 \
    -p MAX_OPERATIONS 1000 \
    -p TIME_OUT 30000
```

Exhaustively explores reachable states.

Look for:
- `No counter example found` - pass (check if complete)
- `all open states visited` - full verification
- `COUNTER EXAMPLE FOUND` - found a bug
- `not all transitions were computed` - incomplete (bounded result)

### 5. Summarize Results

Report in table format:

```
Results:
  Parse:              PASS/FAIL
  Animation:          PASS/WARN/FAIL
  CBC Assertions:     PASS/N/A/FAIL
  CBC Deadlock:       PASS/WARN/N/A
  Model Check:        PASS/WARN/FAIL
```

Include:
- Number of states explored
- Number of transitions fired
- Operations discovered
- Any warnings (unbounded enumeration, incomplete exploration)

### 6. Handle Failures

If errors found:
- Show the counter-example trace
- Explain what invariant/assertion was violated
- Suggest fixes to the specification

## Common Issues

### Unbounded Enumeration

```
Warning: Unbounded enumeration...
```

The spec uses unbounded sets. Add explicit bounds or use smaller setsize.

### Timeout

Increase timeout or reduce exploration scope:
```bash
probcli <file>.tex -model_check -p TIME_OUT 60000 -p DEFAULT_SETSIZE 1
```

### Given Set Cardinality

Explicitly set cardinality for specific given sets:
```bash
probcli <file>.tex -card USERID 3 -model_check
```

## Reference

- probcli options: `reference/probcli-guide.md`
- Z notation: `reference/z-notation.md`
