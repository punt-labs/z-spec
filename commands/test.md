---
description: Validate and animate a Z specification with probcli
argument-hint: "[file.tex] [options: -v verbose, -s N setsize]"
allowed-tools: mcp__plugin_z-spec_zspec__test, mcp__plugin_z-spec_zspec__show_z_spec, Read, Glob
---

# Test Z Specification with ProB

Validate and animate a Z specification using probcli (ProB command line interface).

## Input

Arguments: $ARGUMENTS

Parse arguments:

- First positional argument: file path (or search in `docs/`)
- `-v` or `--verbose`: Show every check's `detail` field, not just the
  summary line (display only — the tool returns structured JSON, not raw
  probcli stdout, so there is no raw output to surface)
- `-s N` or `--setsize N`: Default set size for model checking (default: 2)

`-a` and `-v` are not parameters of the `test` tool. `run_full_suite`
animates a fixed 20 steps internally — custom step counts are the separate
`animate` capability. The tool's `max_ops` (default 1000) bounds
model-checking only, and stays at the default; `-v` merely changes how this
command renders the returned JSON.

## Process

### 1. Locate the Specification

If a file path is provided, use it directly.
If no file specified, look in `docs/` for `.tex` files.

### 2. Verify

Call `mcp__plugin_z-spec_zspec__test` with `file`, plus `setsize` from `-s`.
Leave `max_ops` and `timeout` at the tool defaults — they are not wired to
flags. `-v` is the verbose flag (see step 3), not a tool argument.

The tool runs the five checks — parse-and-init, animation, CBC assertions,
CBC deadlock, model check — and returns:

```
{timestamp, probcli_version, setsize, ok, states_analysed,
 transitions_fired, checks:[{name, status, detail}],
 operations:[{name, times_fired, covered}], counter_example?}
```

It persists `<stem>.report.json` alongside the spec.

### 3. Report

If the returned JSON has an `error` field (e.g. the binary is not installed),
surface `error` (and `hint` if present) verbatim to the user and stop — do not
render the normal result.

Render the JSON as text:

```
Results (setsize N):
  <check.name>: <check.status>   <check.detail>
  ...
States: <states_analysed>   Transitions: <transitions_fired>
Coverage: <count of operations with covered=true>/<len(operations)>
```

If `counter_example` is present, show its `steps` and `violation`, then
explain which invariant or assertion was violated and suggest a fix to the
specification.

### 4. Display

Call `mcp__plugin_z-spec_zspec__show_z_spec` with `file`. It reads the
`<stem>.report.json` just written and renders the Model-Check tab (and a
Counter-Example tab on failure) beside the Spec tab. No hand-rolled lux.

## Common Issues

### Unbounded Enumeration

A check may report unbounded enumeration when the spec uses unbounded sets.
Add explicit cardinality bounds, or lower `-s` (setsize).

### Timeout

The tool's `timeout` stays at its default and is not flag-wired. To keep a
run inside it, reduce `-s` (setsize) to shrink the explored state space.

### Given Set Cardinality

If a specific given set drives state explosion, bound it in the spec with an
axdef constant and a `\#` cardinality constraint rather than relying on the
default setsize.

## Reference

- probcli options: `reference/probcli-guide.md`
- Z notation: `reference/z-notation.md`
