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
| `/z code2model [focus]` | Create or update a Z specification from codebase |
| `/z check [file]` | Type-check a specification with fuzz |
| `/z test [file]` | Validate and animate with probcli |
| `/z partition [spec] [--code [language]] [--operation=NAME] [--json]` | Derive test cases from spec using TTF tactics |
| `/z model2code [spec] [lang]` | Generate code and tests from a Z specification |
| `/z audit [spec] [--json]` | Audit test coverage against spec constraints |
| `/z elaborate [spec] [design]` | Enhance spec with narrative from design docs |
| `/z cleanup [dir]` | Remove TeX tooling files (keeps .tex and .pdf) |
| `/z help` | Show this help |

## Examples

```
/z code2model the user authentication system
/z code2model A library book lending system with members and loans
/z code2model docs/auth.tex add a logout operation  # Update existing
/z check docs/auth.tex
/z test docs/auth.tex -v
/z elaborate docs/auth.tex DESIGN.md
/z elaborate docs/system.tex              # Uses DESIGN.md by default
/z model2code docs/auth.tex swift         # Generate Swift code from spec
/z model2code                             # Auto-detect spec and language
/z partition docs/auth.tex                 # Derive test partitions from spec
/z partition docs/auth.tex --code swift   # Generate partition test code
/z partition --operation=Withdraw          # Partition a single operation
/z audit docs/auth.tex                    # Audit test coverage against spec
/z audit docs/auth.tex --json             # Output as JSON for CI
/z cleanup                                # Remove tooling files from docs/
```

## Automatic TeX File Management

The `/z code2model`, `/z check`, and `/z test` commands automatically:
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

## Reference Files

For detailed documentation, consult:

| File | Contents |
|------|----------|
| `reference/z-notation.md` | Z notation syntax and symbols |
| `reference/schema-patterns.md` | Common schema patterns |
| `reference/latex-style.md` | LaTeX formatting guidelines |
| `reference/probcli-guide.md` | ProB CLI options and usage |
| `reference/test-patterns.md` | Test assertion patterns by language |

## Requirements

**Platform**: macOS or Linux only (Windows not supported)

**Tools**:
- **fuzz**: https://github.com/Spivoxity/fuzz
- **probcli**: https://prob.hhu.de/w/index.php/Download

Set probcli path: `export PROBCLI="$HOME/Applications/ProB/probcli"`
