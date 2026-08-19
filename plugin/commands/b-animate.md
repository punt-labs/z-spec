---
description: Animate and model-check a B machine with probcli
argument-hint: "[machine.mch] [options: -v verbose, -a N animate steps, -s N setsize]"
allowed-tools: Bash(probcli:*), Bash($PROBCLI:*), Bash(which:*), Read, Glob
---

# Animate B Machine with probcli

Animate and model-check a B machine using probcli (ProB command line interface).

## Input

Arguments: $ARGUMENTS

Parse arguments:

- First positional argument: file path (or search in `specs/`)
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
> probcli is not installed. Run `/z-spec:setup probcli` first.

### 1. Locate the Machine

If a file path is provided, use it directly.

If no file specified:

- Look in `specs/` for `.mch` files
- Present options if multiple files exist

### 2. Run Validation Checks

Execute these checks in sequence:

#### Check 1: Parse and Initialize

```bash
probcli <file>.mch -init
```

Verifies the machine parses and has valid initial state(s).

Look for:

- Operation listings indicating available operations
- Error messages indicating parse failures
- `INITIALISATION` execution success

#### Check 2: Animation

```bash
probcli <file>.mch -animate 20
```

Randomly executes operations to verify they're executable.

Look for:

- `ALL OPERATIONS COVERED` - all operations were executed
- Partial coverage indicates some operations may have unsatisfiable preconditions

#### Check 3: Constraint-Based Assertion Check

```bash
probcli <file>.mch -cbc_assertions
```

Checks if any operation can violate assertions defined in the `ASSERTIONS` clause.

Look for:

- `No counter-example to ASSERTION exists` - pass
- `No ASSERTION to check` - no assertions defined
- Counter-example found - potential assertion violation

#### Check 4: Constraint-Based Deadlock Check

```bash
probcli <file>.mch -cbc_deadlock
```

Checks for potential deadlock states (states where no operation is enabled).

Look for:

- `No deadlock possible` - proven deadlock-free
- Deadlock counter-example - may be unreachable (verify with model check)

#### Check 5: Model Checking

```bash
probcli <file>.mch -model_check \
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

### 3. Summarize Results

Report in table format:

```text
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

### 4. Handle Failures

If errors found:

- Show the counter-example trace
- Explain what invariant/assertion was violated
- Suggest fixes to the machine

## Common Issues

### Unbounded Enumeration

```text
Warning: Unbounded enumeration...
```

The machine uses deferred sets without cardinality constraints. Use `-card SET N`
to set specific cardinality for animation.

### Timeout

Increase timeout or reduce exploration scope:

```bash
probcli <file>.mch -model_check -p TIME_OUT 60000 -p DEFAULT_SETSIZE 1
```

### Deferred Set Cardinality

Explicitly set cardinality for deferred sets:

```bash
probcli <file>.mch -card ID 3 -model_check
```

## Reference

- B notation: `reference/b-notation.md`
- B machine patterns: `reference/b-machine-patterns.md`
- probcli options: `reference/probcli-guide.md`
