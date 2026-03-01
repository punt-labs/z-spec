---
description: Show Z specification plugin help and quick reference
---

# Z Specification Plugin Help

## First Time? Start Here

```
/z-spec:setup          # Check what's installed
/z-spec:setup all      # Install fuzz and probcli with guidance
```

## Commands

| Command | Description |
|---------|-------------|
| `/z-spec:setup` | Install and configure fuzz and probcli |
| `/z-spec:doctor` | Check Z specification environment health |
| `/z-spec:code2model [focus]` | Create or update a Z specification from codebase |
| `/z-spec:check [file]` | Type-check a specification with fuzz |
| `/z-spec:test [file]` | Validate and animate with probcli |
| `/z-spec:partition [spec] [--code [language]] [--operation=NAME] [--json]` | Derive test cases from spec using TTF tactics |
| `/z-spec:model2code [spec] [lang]` | Generate code and tests from a Z specification |
| `/z-spec:prove [spec] [--obligations=all\|init\|preserve] [--no-mathlib]` | Generate Lean 4 proof obligations from spec |
| `/z-spec:contracts [spec] [lang] [--invariants-only] [--wrap]` | Generate runtime contracts (pre/post/invariant) from spec |
| `/z-spec:oracle [spec] [lang] [--sequences N] [--steps N]` | Property-based testing with Lean model as oracle |
| `/z-spec:refine [spec] [lang] [--lean] [--generate-abstraction]` | Verify code refines spec via abstraction function |
| `/z-spec:audit [spec] [--json]` | Audit test coverage against spec constraints |
| `/z-spec:elaborate [spec] [design]` | Enhance spec with narrative from design docs |
| `/z-spec:cleanup [dir]` | Remove TeX tooling files (keeps .tex and .pdf) |
| `/z-spec:help` | Show this help |

### B-Method Commands

| Command | Description |
|---------|-------------|
| `/z-spec:b-create [description or file.tex]` | Create a B machine or translate Z spec to B |
| `/z-spec:b-check [machine.mch]` | Type-check a B machine with probcli |
| `/z-spec:b-animate [machine.mch]` | Animate and model-check a B machine |
| `/z-spec:b-refine [machine.mch] [refinement.ref]` | Create or verify a B refinement |

## Examples

```
/z-spec:code2model the user authentication system
/z-spec:code2model A library book lending system with members and loans
/z-spec:code2model docs/auth.tex add a logout operation  # Update existing
/z-spec:check docs/auth.tex
/z-spec:test docs/auth.tex -v
/z-spec:elaborate docs/auth.tex DESIGN.md
/z-spec:elaborate docs/system.tex              # Uses DESIGN.md by default
/z-spec:model2code docs/auth.tex swift         # Generate Swift code from spec
/z-spec:model2code                             # Auto-detect spec and language
/z-spec:partition docs/auth.tex                 # Derive test partitions from spec
/z-spec:partition docs/auth.tex --code swift   # Generate partition test code
/z-spec:partition --operation=Withdraw          # Partition a single operation
/z-spec:prove docs/auth.tex                    # Generate Lean 4 proof obligations
/z-spec:prove docs/auth.tex --no-mathlib       # Standalone Lean (no Mathlib)
/z-spec:contracts docs/auth.tex typescript     # Generate runtime assertion functions
/z-spec:contracts docs/auth.tex --wrap         # With wrapper functions
/z-spec:oracle docs/auth.tex typescript        # Property-based testing vs Lean model
/z-spec:refine docs/auth.tex typescript        # Verify code refines spec
/z-spec:refine docs/auth.tex --generate-abstraction  # Auto-scaffold abstraction fn
/z-spec:audit docs/auth.tex                    # Audit test coverage against spec
/z-spec:audit docs/auth.tex --json             # Output as JSON for CI
/z-spec:doctor                                 # Check environment health
/z-spec:cleanup                                # Remove tooling files from docs/
```

### B-Method Examples

```
/z-spec:b-create A counter with increment and reset     # B machine from description
/z-spec:b-create docs/counter.tex                       # Translate Z spec to B machine
/z-spec:b-check specs/counter.mch                       # Type-check B machine
/z-spec:b-animate specs/counter.mch                     # Animate and model-check
/z-spec:b-refine specs/counter.mch                      # Create refinement machine
/z-spec:b-refine specs/counter.mch specs/counter_r.ref  # Verify existing refinement
```

## Automatic TeX File Management

The `/z-spec:code2model`, `/z-spec:check`, and `/z-spec:test` commands automatically:
1. Copy `fuzz.sty` and Metafont files to `docs/` if missing
2. Add appropriate patterns to `.gitignore`

Use `/z-spec:cleanup` to remove these tooling files when done. Your `.tex` source and `.pdf` output are preserved.

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
| `reference/lean4-patterns.md` | Z-to-Lean 4 translation patterns |
| `reference/b-notation.md` | B-Method notation syntax and types |
| `reference/b-machine-patterns.md` | B machine patterns and Z-to-B translation |

## Requirements

**Platform**: macOS or Linux only (Windows not supported)

**Tools**:

- **fuzz**: https://github.com/Spivoxity/fuzz
- **probcli**: https://prob.hhu.de/w/index.php/Download
- **lean** (optional): https://lean-lang.org/install/ (for `/z-spec:prove`, `/z-spec:oracle`, `/z-spec:refine --lean`)

Set probcli path: `export PROBCLI="$HOME/Applications/ProB/probcli"`
