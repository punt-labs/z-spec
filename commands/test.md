---
description: Validate and animate a Z specification with probcli
argument-hint: "[file.tex] [options: -v verbose, -a N animate steps, -s N setsize]"
allowed-tools: Bash(probcli:*), Bash($PROBCLI:*), Bash(fuzz:*), Bash(which:*), Bash(pdflatex:*), Read, Glob, mcp__plugin_lux_lux__ping, mcp__plugin_lux_lux__show
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
> probcli is not installed. Run `/z-spec:setup` first to install the Z specification tools.

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

### 6. Visual Display (when lux available)

After summarizing results in text, attempt to render an interactive lux dashboard.

#### 6a. Check Lux Availability

Try calling `mcp__plugin_lux_lux__ping`. If it succeeds, lux is available.
If it fails or the tool does not exist, skip to Step 7 (text-only output is sufficient).

> **Note**: Once lux-t1p ships, replace this ping check with reading `.lux/config.md` instead.

#### 6b. Compose Dashboard

Call `mcp__plugin_lux_lux__show` with a JSON scene:

```json
{
  "scene_id": "z-spec-test-results",
  "title": "<spec filename> — Model Check Results",
  "elements": [
    {"kind": "group", "id": "metrics", "layout": "columns", "children": [
      {"kind": "text", "id": "m_states", "content": "States: <N>"},
      {"kind": "text", "id": "m_trans", "content": "Transitions: <N>"},
      {"kind": "text", "id": "m_coverage", "content": "Coverage: <N/M ops>"},
      {"kind": "text", "id": "m_result", "content": "Result: PASS|FAIL"}
    ]},
    {"kind": "separator"},
    {"kind": "table", "id": "checks", "columns": ["Check", "Result", "Details"],
     "rows": [
       ["Parse & Init", "PASS|FAIL", "<details>"],
       ["Animation", "PASS|WARN|FAIL", "<coverage info>"],
       ["CBC Assertions", "PASS|N/A|FAIL", "<details>"],
       ["CBC Deadlock", "PASS|WARN|N/A", "<details>"],
       ["Model Check", "PASS|WARN|FAIL", "<states/transitions>"]
     ], "flags": ["borders", "row_bg"]},
    {"kind": "separator"},
    {"kind": "table", "id": "ops_coverage", "columns": ["Operation", "Times Fired", "Status"],
     "rows": [
       ["<op1>", "<count>", "✓ covered|✗ uncovered"],
       ["<op2>", "<count>", "✓ covered|✗ uncovered"]
     ], "flags": ["borders", "row_bg", "resizable"]}
  ]
}
```

Populate the placeholders from the probcli output parsed in Steps 4–5:
- **States**: from `States analysed: N` in model check output
- **Transitions**: from `Transitions fired: N` in model check output
- **Coverage**: count of operations that were fired at least once vs total operations
- **Result**: "PASS" if no counter-example and all checks passed; "FAIL" otherwise
- **Operation rows**: one per operation discovered in Step 4, with fire count from animation output

#### 6c. Counter-Example Trace (when failure found)

If `COUNTER EXAMPLE FOUND` appears in the probcli output, render a trace diagram
as a **second tab** in the dashboard. Replace the simple `elements` array with a
`tab_bar` containing both the dashboard and the trace:

```json
{
  "scene_id": "z-spec-test-results",
  "title": "<spec filename> — Model Check Results",
  "elements": [
    {"kind": "tab_bar", "id": "result_tabs", "tabs": [
      {"label": "Dashboard", "children": [
        {"kind": "group", "id": "metrics", "layout": "columns", "children": [
          {"kind": "text", "id": "m_states", "content": "States: <N>"},
          {"kind": "text", "id": "m_trans", "content": "Transitions: <N>"},
          {"kind": "text", "id": "m_coverage", "content": "Coverage: <N/M ops>"},
          {"kind": "text", "id": "m_result", "content": "Result: FAIL"}
        ]},
        {"kind": "separator"},
        {"kind": "table", "id": "checks", "columns": ["Check", "Result", "Details"],
         "rows": ["... same as 6b ..."],
         "flags": ["borders", "row_bg"]},
        {"kind": "separator"},
        {"kind": "table", "id": "ops_coverage", "columns": ["Operation", "Times Fired", "Status"],
         "rows": ["... same as 6b ..."],
         "flags": ["borders", "row_bg", "resizable"]}
      ]},
      {"label": "Counter-Example Trace", "children": [
        {"kind": "markdown", "id": "trace_header", "content": "## Counter-Example Trace\n\nThe model checker found a state sequence that violates an invariant or assertion."},
        {"kind": "table", "id": "trace_steps", "columns": ["Step", "Operation", "State After"],
         "rows": [
           ["0", "INITIALISATION", "<var1=val1, var2=val2, ...>"],
           ["1", "<OperationName>", "<var1=val1', var2=val2', ...>"],
           ["N", "VIOLATION", "<violating state values>"]
         ], "flags": ["borders", "row_bg"]},
        {"kind": "separator"},
        {"kind": "markdown", "id": "trace_explain", "content": "**Violated**: <invariant or assertion text>\n\n**Explanation**: <why this state sequence leads to violation>"}
      ]}
    ]}
  ]
}
```

Parse the counter-example trace from probcli output:
- Each step appears as `N: OperationName(params)` or `SETUP_CONSTANTS` / `INITIALISATION`
- State dumps appear as `STATE = (var1=val1 & var2=val2 & ...)`
- The final step is the violation — extract which invariant or assertion failed

#### 6d. Graceful Degradation

If the lux `show` call fails for any reason (tool unavailable, malformed JSON, etc.),
continue with text-only output. Do not retry or error — lux supplements the
conversation, it never replaces it.

### 7. Handle Failures

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
