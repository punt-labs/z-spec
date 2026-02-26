---
description: Check Z specification environment health
allowed-tools: Bash(which:*), Bash(fuzz:*), Bash(probcli:*), Bash($PROBCLI:*), Bash(kpsewhich:*), Bash(brew:*), Bash(test:*), Bash(uname:*), Read
---

# Z Environment Health Check

Run diagnostic checks on the Z specification toolchain and report results in a status table.

## Checks

Run all checks, collecting results before producing output. Run independent checks in parallel where possible.

### 1. Platform (informational)

```bash
uname -s   # Darwin or Linux
uname -m   # arm64, x86_64, etc.
```

### 2. fuzz binary (required)

```bash
which fuzz && fuzz -version
```

If missing: suggest `Run /z setup fuzz`.

### 3. fuzz.sty (required)

```bash
kpsewhich fuzz.sty
```

If missing: suggest `Run /z setup fuzz` then `sudo texhash`.

### 4. probcli binary (required)

```bash
which probcli || test -x "$HOME/Applications/ProB/probcli"
```

Also check `$PROBCLI` if set. If missing: suggest `Run /z setup probcli`.

### 5. Tcl/Tk (conditional — macOS only)

Only check on Darwin:

```bash
which wish || brew list tcl-tk 2>/dev/null
```

If missing on macOS: suggest `brew install tcl-tk`.

## Output Format

Present results as a status table, then a summary:

```
## Environment

| Check | Status |
|-------|--------|
| Platform | macOS arm64 |
| fuzz | ✓ Installed (version 3.4.1) |
| fuzz.sty | ✓ Found at /usr/local/texlive/.../fuzz.sty |
| probcli | ✗ Not found |
| Tcl/Tk | ✓ Available |

## Result

1 issue found. Run `/z setup` to install missing tools.
```

If all checks pass:

```
## Result

All checks passed. Environment is ready for Z specification work.
```

## Remediation

For each failure, include a specific actionable fix in the Status column or below the table. Point users to `/z setup` for installation.
