---
description: Show Z specification plugin help and quick reference
---

# Z Specification Plugin Help

## First Time? Start Here

```
/z-spec-dev:setup-dev          # Check what's installed
/z-spec-dev:setup-dev all      # Install fuzz and probcli with guidance
```

## Commands

| Command | Description |
|---------|-------------|
| `/z-spec-dev:setup-dev` | Install and configure fuzz and probcli |
| `/z-spec-dev:doctor-dev` | Check Z specification environment health |
| `/z-spec-dev:code2model-dev [focus]` | Create or update a Z specification from codebase |
| `/z-spec-dev:check-dev [file]` | Type-check a specification with fuzz |
| `/z-spec-dev:test-dev [file]` | Validate and animate with probcli |
| `/z-spec-dev:partition-dev [spec] [--code [language]] [--operation=NAME] [--json]` | Derive test cases from spec using TTF tactics |
| `/z-spec-dev:model2code-dev [spec] [lang]` | Generate code and tests from a Z specification |
| `/z-spec-dev:prove-dev [spec] [--obligations=all\|init\|preserve] [--no-mathlib]` | Generate Lean 4 proof obligations from spec |
| `/z-spec-dev:contracts-dev [spec] [lang] [--invariants-only] [--wrap]` | Generate runtime contracts (pre/post/invariant) from spec |
| `/z-spec-dev:oracle-dev [spec] [lang] [--sequences N] [--steps N]` | Property-based testing with Lean model as oracle |
| `/z-spec-dev:refine-dev [spec] [lang] [--lean] [--generate-abstraction]` | Verify code refines spec via abstraction function |
| `/z-spec-dev:audit-dev [spec] [--json]` | Audit test coverage against spec constraints |
| `/z-spec-dev:elaborate-dev [spec] [design]` | Enhance spec with narrative from design docs |
| `/z-spec-dev:cleanup-dev [dir]` | Remove TeX tooling files (keeps .tex and .pdf) |
| `/z-spec-dev:help-dev` | Show this help |

### B-Method Commands

| Command | Description |
|---------|-------------|
| `/z-spec-dev:b-create-dev [description or file.tex]` | Create a B machine or translate Z spec to B |
| `/z-spec-dev:b-check-dev [machine.mch]` | Type-check a B machine with probcli |
| `/z-spec-dev:b-animate-dev [machine.mch]` | Animate and model-check a B machine |
| `/z-spec-dev:b-refine-dev [machine.mch] [refinement.ref]` | Create or verify a B refinement |

## Examples

```
/z-spec-dev:code2model-dev the user authentication system
/z-spec-dev:code2model-dev A library book lending system with members and loans
/z-spec-dev:code2model-dev docs/auth.tex add a logout operation  # Update existing
/z-spec-dev:check-dev docs/auth.tex
/z-spec-dev:test-dev docs/auth.tex -v
/z-spec-dev:elaborate-dev docs/auth.tex DESIGN.md
/z-spec-dev:elaborate-dev docs/system.tex              # Uses DESIGN.md by default
/z-spec-dev:model2code-dev docs/auth.tex swift         # Generate Swift code from spec
/z-spec-dev:model2code-dev                             # Auto-detect spec and language
/z-spec-dev:partition-dev docs/auth.tex                 # Derive test partitions from spec
/z-spec-dev:partition-dev docs/auth.tex --code swift   # Generate partition test code
/z-spec-dev:partition-dev --operation=Withdraw          # Partition a single operation
/z-spec-dev:prove-dev docs/auth.tex                    # Generate Lean 4 proof obligations
/z-spec-dev:prove-dev docs/auth.tex --no-mathlib       # Standalone Lean (no Mathlib)
/z-spec-dev:contracts-dev docs/auth.tex typescript     # Generate runtime assertion functions
/z-spec-dev:contracts-dev docs/auth.tex --wrap         # With wrapper functions
/z-spec-dev:oracle-dev docs/auth.tex typescript        # Property-based testing vs Lean model
/z-spec-dev:refine-dev docs/auth.tex typescript        # Verify code refines spec
/z-spec-dev:refine-dev docs/auth.tex --generate-abstraction  # Auto-scaffold abstraction fn
/z-spec-dev:audit-dev docs/auth.tex                    # Audit test coverage against spec
/z-spec-dev:audit-dev docs/auth.tex --json             # Output as JSON for CI
/z-spec-dev:doctor-dev                                 # Check environment health
/z-spec-dev:cleanup-dev                                # Remove tooling files from docs/
```

### B-Method Examples

```
/z-spec-dev:b-create-dev A counter with increment and reset     # B machine from description
/z-spec-dev:b-create-dev docs/counter.tex                       # Translate Z spec to B machine
/z-spec-dev:b-check-dev specs/counter.mch                       # Type-check B machine
/z-spec-dev:b-animate-dev specs/counter.mch                     # Animate and model-check
/z-spec-dev:b-refine-dev specs/counter.mch                      # Create refinement machine
/z-spec-dev:b-refine-dev specs/counter.mch specs/counter_r.ref  # Verify existing refinement
```

## Automatic TeX File Management

The `/z-spec-dev:code2model-dev`, `/z-spec-dev:check-dev`, and `/z-spec-dev:test-dev` commands automatically:
1. Copy `fuzz.sty` and Metafont files to `docs/` if missing
2. Add appropriate patterns to `.gitignore`

Use `/z-spec-dev:cleanup-dev` to remove these tooling files when done. Your `.tex` source and `.pdf` output are preserved.

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
- **lean** (optional): https://lean-lang.org/install/ (for `/z-spec-dev:prove-dev`, `/z-spec-dev:oracle-dev`, `/z-spec-dev:refine-dev --lean`)

Set probcli path: `export PROBCLI="$HOME/Applications/ProB/probcli"`
