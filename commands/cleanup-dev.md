---
description: Remove Z specification tooling files from project
argument-hint: "[docs-dir]"
allowed-tools: Bash(which:*), Read, Glob
---

# Cleanup Z Specification Files

Remove auto-managed TeX tooling files from the project while preserving source specs and PDF output.

## Input

Arguments: $ARGUMENTS

- Directory path (default: `docs/`)

## Files to Remove

**TeX tooling (auto-copied by /z commands):**
- `fuzz.sty` - LaTeX style file
- `*.mf` - Metafont source files
- `*.pk` - Packed font files
- `*.tfm` - TeX font metrics

**Build intermediates:**
- `*.aux` - LaTeX auxiliary
- `*.log` - LaTeX log
- `*.fuzz` - fuzz output
- `*.toc` - Table of contents

## Files to Keep

- `*.tex` - Z specification source files
- `*.pdf` - Compiled PDF output

## Process

### 1. Confirm Directory

```bash
DOCS_DIR="${1:-docs}"
if [ ! -d "$DOCS_DIR" ]; then
    echo "Directory not found: $DOCS_DIR"
    exit 1
fi
```

### 2. List Files to Remove

Before removing, show what will be deleted:

```bash
echo "Files to remove from $DOCS_DIR:"
ls -la "$DOCS_DIR"/fuzz.sty "$DOCS_DIR"/*.mf "$DOCS_DIR"/*.pk "$DOCS_DIR"/*.tfm \
       "$DOCS_DIR"/*.aux "$DOCS_DIR"/*.log "$DOCS_DIR"/*.fuzz "$DOCS_DIR"/*.toc 2>/dev/null
```

### 3. Remove Files

```bash
cd "$DOCS_DIR"

# TeX tooling
rm -f fuzz.sty
rm -f *.mf *.pk *.tfm

# Build intermediates
rm -f *.aux *.log *.fuzz *.toc
```

### 4. Report Results

```bash
echo ""
echo "Cleanup complete. Remaining files:"
ls -la "$DOCS_DIR"/*.tex "$DOCS_DIR"/*.pdf 2>/dev/null || echo "No .tex or .pdf files"
```

## Output

Report what was removed and what remains:

```
## Cleanup Complete

Removed from docs/:
- fuzz.sty
- 10 Metafont files (*.mf)
- 3 font files (*.pk, *.tfm)
- 4 build files (*.aux, *.log, *.fuzz, *.toc)

Preserved:
- koch_trainer.tex (source)
- koch_trainer.pdf (output)
```
