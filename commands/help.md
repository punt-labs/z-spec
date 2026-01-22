---
description: Show Z specification plugin help and quick reference
---

# Z Specification Plugin Help

## First Time? Start Here

```
/z setup          # Check what's installed
/z setup all      # Install fuzz and probcli with guidance
```

## Commands

| Command | Description |
|---------|-------------|
| `/z setup` | Install and configure fuzz and probcli |
| `/z create [focus]` | Generate a Z specification from codebase or description |
| `/z check [file]` | Type-check a specification with fuzz |
| `/z test [file]` | Validate and animate with probcli |
| `/z update [file] [changes]` | Modify an existing specification |
| `/z elaborate [spec] [design]` | Enhance spec with narrative from design docs |
| `/z cleanup [dir]` | Remove TeX tooling files (keeps .tex and .pdf) |
| `/z help` | Show this help |

## Examples

```
/z create the user authentication system
/z create A library book lending system with members and loans
/z check docs/auth.tex
/z test docs/auth.tex -v
/z update docs/auth.tex add a logout operation
/z elaborate docs/auth.tex DESIGN.md
/z elaborate docs/system.tex              # Uses DESIGN.md by default
/z cleanup                                # Remove tooling files from docs/
```

## Automatic TeX File Management

The `/z create`, `/z check`, and `/z test` commands automatically:
1. Copy `fuzz.sty` and Metafont files to `docs/` if missing
2. Add appropriate patterns to `.gitignore`

Use `/z cleanup` to remove these tooling files when done. Your `.tex` source and `.pdf` output are preserved.

## Quick Z Reference

### Document Structure
```latex
\begin{zed}[USERID, TIMESTAMP]\end{zed}     % Given sets
\begin{zed}Status ::= active | inactive\end{zed}  % Free types
\begin{schema}{Name}...\end{schema}          % State schema
\begin{axdef}...\end{axdef}                  % Constants
```

### Common Types
| Syntax | Meaning |
|--------|---------|
| `\nat` | Natural numbers |
| `\power X` | Power set of X |
| `\pfun` | Partial function |
| `\pinj` | Partial injection (unique values) |
| `\seq X` | Sequence of X |

### Schema Conventions
| Syntax | Meaning |
|--------|---------|
| `\Delta S` | State change (includes S and S') |
| `\Xi S` | No state change |
| `x?` | Input |
| `x!` | Output |
| `x'` | After-state |

### Validation
```bash
fuzz -t file.tex          # Type-check
probcli file.tex -init    # Parse
probcli file.tex -animate 20   # Animate
probcli file.tex -model_check  # Model check
```

## ProB Compatibility Tips

For specs that work with both fuzz and probcli:

| Issue | Solution |
|-------|----------|
| B keyword conflict | Use `ZBOOL ::= ztrue \| zfalse` (not BOOL/true/false) |
| Abstract functions | Provide concrete mappings: `f = \{ 1 \mapsto a, ... \}` |
| Unbounded integers | Add bounds: `count \leq 1000` |
| Unbounded inputs | Add bounds: `accuracy? \leq 100` |
| Nested schema types | Flatten all fields into one `State` schema |
| Missing Init | Create unified `Init` schema with all initial values |
| Init with schema composition | Avoid `\theta` and dot notation on primed schemas |

## Requirements

- **fuzz**: https://github.com/Spivoxity/fuzz
- **probcli**: https://prob.hhu.de/w/index.php/Download

Set probcli path: `export PROBCLI="$HOME/Applications/ProB/probcli"`
