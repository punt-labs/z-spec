---
description: Check Z specification environment health
allowed-tools: mcp__plugin_z-spec-dev_zspec__doctor, Bash(kpsewhich:*), Bash(brew:*), Bash(command:*), Bash(test:*), Bash(uname:*), Bash(elan:*), Bash(lean:*), Bash(lake:*), Read
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

### 2. Required toolchain (fuzz, probcli, plugin version)

Call `mcp__plugin_z-spec-dev_zspec__doctor`. It returns
`{version, fuzz, probcli, healthy}` — the plugin `version` string, the
resolved `fuzz` and `probcli` binary **paths** (or `null` when absent), and
an overall `healthy` flag for the required pair.

Report fuzz and probcli as presence, not version: `installed (<path>)` when
the path field is set, `not found` when it is `null`. Do not report fuzz or
probcli binary version strings — the tool does not provide them. (Binary
versions return once `DoctorReport` is widened; that work is beaded.)

- `fuzz` null: suggest `Run /z-spec-dev:setup-dev fuzz`.
- `probcli` null: suggest `Run /z-spec-dev:setup-dev probcli`.

probcli handles both Z specifications (`.tex`) and B machines (`.mch`, `.ref`, `.imp`).

### 3. fuzz.sty (required)

```bash
kpsewhich fuzz.sty
```

If missing: suggest `Run /z-spec-dev:setup-dev fuzz` then `sudo texhash`.

### 4. Tcl/Tk (conditional — macOS only)

Only check on Darwin. Present if EITHER Homebrew has `tcl-tk` OR `wish` is on
PATH (catches installs outside Homebrew). The probe always prints one line,
so the status table populates even when `brew` is absent:

```bash
brew list tcl-tk >/dev/null 2>&1 || command -v wish >/dev/null 2>&1 && echo "Tcl/Tk: installed" || echo "Tcl/Tk: not found"
```

If it prints `not found` on macOS: suggest `brew install tcl-tk`.

### 5. elan (optional — for /z-spec-dev:prove-dev)

```bash
command -v elan >/dev/null 2>&1 && elan --version || echo "elan: not installed"
```

If missing: suggest `Run /z-spec-dev:setup-dev lean`.

### 6. lean (optional — for /z-spec-dev:prove-dev)

```bash
command -v lean >/dev/null 2>&1 && lean --version || echo "lean: not installed"
```

If missing but elan is present: suggest `elan default leanprover/lean4:stable`.

### 7. lake (optional — for /z-spec-dev:prove-dev)

```bash
command -v lake >/dev/null 2>&1 && lake --version || echo "lake: not installed"
```

Usually installed alongside lean via elan.

## Output Format

Present results as a status table, then a summary:

```
## Environment

| Check | Status |
|-------|--------|
| Platform | macOS arm64 |
| Plugin | ✓ version 0.16.0 |
| fuzz | ✓ Installed (/opt/homebrew/bin/fuzz) |
| fuzz.sty | ✓ Found at /usr/local/texlive/.../fuzz.sty |
| probcli | ✗ Not found |
| Tcl/Tk | ✓ Available |
| elan | ✓ Installed (version 3.1.1) |
| lean | ✓ Installed (v4.16.0) |
| lake | ✓ Installed (v4.16.0) |

## Result

1 issue found. Run `/z-spec-dev:setup-dev` to install missing tools.
```

If all checks pass:

```
## Result

All checks passed. Environment is ready for Z specification work.
```

## Remediation

For each failure, include a specific actionable fix in the Status column or below the table. Point users to `/z-spec-dev:setup-dev` for installation.
