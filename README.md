# Z Specification Plugin for Claude Code

> Formal Z specifications and B machines that type-check, animate, and refine --- from English to math to code.

[![License](https://img.shields.io/github/license/punt-labs/z-spec)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/punt-labs/z-spec/docs.yml?label=CI)](https://github.com/punt-labs/z-spec/actions/workflows/docs.yml)

**Platforms:** macOS, Linux

## What is Z?

[Z](https://en.wikipedia.org/wiki/Z_notation) ("zed") is a formal specification language based on set theory and first-order predicate logic. It was developed at the University of Oxford in the late 1970s and is standardized as [ISO 13568](https://www.iso.org/standard/21573.html).

A Z specification describes a system as:

- **States** --- the data a system holds (e.g., a set of users, a counter, a mode flag)
- **Invariants** --- constraints that must always be true (e.g., `correct ≤ attempts`, `level ≥ 1`)
- **Operations** --- transitions between states, with preconditions and effects

The specification says *what* a system does, not *how*. When a type-checker ([fuzz](https://spivey.oriel.ox.ac.uk/mike/fuzz/)) accepts a spec, the description is internally consistent. When an animator ([ProB](https://prob.hhu.de/)) explores the state space, you see every reachable configuration --- including ones you forgot to think about.

Z's sibling, the [B-Method](https://en.wikipedia.org/wiki/B-Method), extends the same mathematical foundations with a substitution language and a deterministic refinement chain from spec to code. This plugin supports both --- see [B-Method](#b-method-workflow-alpha) below.

### Why use formal specs?

Formal specs catch entire *classes* of bugs mathematically, not just the specific inputs you happened to test. A spec invariant like `¬(radioMode = receiving ∧ toneActive)` makes it structurally impossible to miss the case where keying occurs during receive mode --- no matter how many test cases you write, the invariant covers all of them.

Formal specifications have always caught these bugs. They were too expensive to write by hand --- hours of skilled effort per schema. An LLM drafts the spec; fuzz type-checks it. The methods are the same; the time cost is not.

### Key references

- Spivey, J.M. *[The Z Notation: A Reference Manual](https://spivey.oriel.ox.ac.uk/mike/zrm/)* --- the definitive Z reference
- Abrial, J-R. *[The B-Book: Assigning Programs to Meanings](https://doi.org/10.1017/CBO9780511624162)* --- the definitive B-Method reference, by Z's co-creator
- Bowen, J.P. *[Formal Specification and Documentation using Z](https://doi.org/10.1007/978-1-4471-3553-1)* --- practical applications of Z to real systems
- Simpson, A. *Software Engineering Mathematics* and *State-Based Modelling* --- [University of Oxford](https://www.cs.ox.ac.uk/), Department of Computer Science

## Dependencies

Z Spec orchestrates two established tools that do the mathematical heavy lifting:

- **[fuzz](https://spivey.oriel.ox.ac.uk/mike/fuzz/)** --- Mike Spivey's Z type-checker, developed at Oxford. Verifies that a specification is internally consistent: every schema is well-typed, every reference resolves, every invariant is expressible. Also provides `fuzz.sty` for LaTeX rendering.
- **[ProB](https://prob.hhu.de/)** --- an animator and model-checker from Heinrich Heine University Düsseldorf. Explores the state space of a specification: finds reachable states, checks invariants hold across all transitions, and discovers counter-examples when they don't.

Both are installed automatically by `/z-spec:setup all`. fuzz is compiled from source; ProB is downloaded as a pre-built binary for your platform.

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/punt-labs/z-spec/f0e8132/install.sh | sh
```

<details>
<summary>Manual install (if you already have the marketplace)</summary>

```bash
claude plugin install z-spec@punt-labs
```

</details>

<details>
<summary>Verify before running</summary>

```bash
curl -fsSL https://raw.githubusercontent.com/punt-labs/z-spec/f0e8132/install.sh -o install.sh
shasum -a 256 install.sh
cat install.sh
sh install.sh
```

</details>

Inside Claude Code:

```
/z-spec:setup all                                   # Install fuzz and probcli
/z-spec:code2model the user authentication system   # Generate your first spec
/z-spec:check docs/auth.tex                         # Type-check it
/z-spec:test docs/auth.tex                          # Animate and model-check
```

<details>
<summary>What /z-spec:setup installs</summary>

- **fuzz** --- Z type-checker ([source](https://github.com/Spivoxity/fuzz)), includes `fuzz.sty` for LaTeX
- **probcli** --- ProB CLI for animation and model-checking ([download](https://prob.hhu.de/w/index.php/Download)), requires Tcl/Tk
- **lean** (optional) --- Lean 4 theorem prover for `/z-spec:prove` ([install](https://lean-lang.org/install/))

Setup auto-detects your platform (macOS Intel/Apple Silicon, Linux) and guides you through each install.

</details>

## What It Looks Like

### A generated spec

```latex
\begin{schema}{State}
level : \nat \\
attempts : \nat \\
correct : \nat
\where
level \geq 1 \\
level \leq 26 \\
correct \leq attempts \\
attempts \leq 10000
\end{schema}

\begin{schema}{AdvanceLevel}
\Delta State \\
accuracy? : \nat
\where
accuracy? \geq 90 \\
accuracy? \leq 100 \\
level < 26 \\
level' = level + 1 \\
attempts' = attempts \\
correct' = correct
\end{schema}
```

### A derived partition table

`/z-spec:partition` applies the [Test Template Framework](https://doi.org/10.1007/3-540-48257-1_11) (TTF) to derive conformance test cases directly from the spec's mathematics:

1. **DNF decomposition** --- split disjunctions into independent behavioral branches
2. **Standard partitions** --- type-based equivalence classes (endpoints, midpoints, every constructor)
3. **Boundary analysis** --- values at and around each constraint edge

For the `AdvanceLevel` schema above:

| # | Class | Inputs | Pre-state | Expected |
|---|-------|--------|-----------|----------|
| 1 | Happy path | accuracy=95 | level=5 | level'=6 |
| 2 | Boundary: min accuracy | accuracy=90 | level=5 | level'=6 |
| 3 | Boundary: max level | accuracy=95 | level=25 | level'=26 |
| 4 | Rejected: low accuracy | accuracy=89 | level=5 | no change |
| 5 | Rejected: at max | accuracy=95 | level=26 | no change |

Add `--code swift` (or python, typescript, kotlin) to generate executable test cases.

## Features

- **Generate Z specs** from codebase analysis or system descriptions (`/z-spec:code2model`)
- **Type-check** with fuzz (`/z-spec:check`)
- **Animate and model-check** with probcli (`/z-spec:test`)
- **Derive test cases** from specs using TTF testing tactics (`/z-spec:partition`)
- **Generate code and tests** from specifications (`/z-spec:model2code`)
- **Audit test coverage** against spec constraints (`/z-spec:audit`)
- **Generate Lean 4 proof obligations** for machine-checked correctness (`/z-spec:prove`)
- **Generate runtime contracts** (preconditions, postconditions, invariants) from specs (`/z-spec:contracts`)
- **Property-based testing** with Lean model as oracle (`/z-spec:oracle`)
- **Data refinement verification** via abstraction function commutativity (`/z-spec:refine`)
- **Elaborate** specs with narrative from design documentation (`/z-spec:elaborate`)
- **ProB-compatible** output (avoids B keyword conflicts, bounded integers, flat schemas)
- **B-Method support** (alpha) --- create, type-check, animate, and refine B machines (`/z-spec:b-create`, `/z-spec:b-check`, `/z-spec:b-animate`, `/z-spec:b-refine`)

## Commands

### Setup

| Command | Description |
|---------|-------------|
| `/z-spec:setup [check\|fuzz\|probcli\|all]` | Install and configure fuzz and probcli |
| `/z-spec:doctor` | Check environment health |
| `/z-spec:help` | Show quick reference |
| `/z-spec:cleanup [dir]` | Remove TeX tooling files (keeps .tex and .pdf) |

### Z Specification

| Command | Description |
|---------|-------------|
| `/z-spec:code2model [focus]` | Create a Z spec from codebase or description |
| `/z-spec:check [file]` | Type-check with fuzz |
| `/z-spec:test [file] [-v] [-a N] [-s N]` | Animate and model-check with probcli |
| `/z-spec:elaborate [spec] [design]` | Enhance spec with narrative from design docs |
| `/z-spec:prove [spec] [--obligations=all\|init\|preserve] [--no-mathlib]` | Generate Lean 4 proof obligations |
| `/z-spec:partition [spec] [--code [language]] [--operation=NAME] [--json]` | Derive test cases using TTF testing tactics |
| `/z-spec:model2code [spec] [language]` | Generate code and tests from spec |
| `/z-spec:contracts [spec] [language] [--invariants-only] [--wrap] [--strip]` | Generate runtime assertion functions |
| `/z-spec:oracle [spec] [language] [--sequences N] [--steps N]` | Property-based testing with Lean model as oracle |
| `/z-spec:refine [spec] [language] [--lean] [--generate-abstraction] [--impl file]` | Verify code refines spec via abstraction function |
| `/z-spec:audit [spec] [--json] [--test-dir=DIR]` | Audit test coverage against spec constraints |

### B-Method (alpha)

| Command | Description |
|---------|-------------|
| `/z-spec:b-create [description or file.tex]` | Create a B machine or translate Z spec to B |
| `/z-spec:b-check [machine.mch]` | Type-check with probcli |
| `/z-spec:b-animate [machine.mch]` | Animate and model-check with probcli |
| `/z-spec:b-refine [machine.mch] [refinement.ref]` | Create or verify a refinement |

## Workflow

```
/z-spec:setup                              # Install tools (first time only)
/z-spec:doctor                             # Verify environment health
/z-spec:code2model the payment system      # Generate spec from codebase
/z-spec:check docs/payment.tex             # Type-check
/z-spec:test docs/payment.tex              # Animate and model-check
/z-spec:partition docs/payment.tex         # Derive test cases from spec
/z-spec:partition docs/payment.tex --code  # Generate executable test code
/z-spec:prove docs/payment.tex             # Generate Lean 4 proof obligations
/z-spec:contracts docs/payment.tex         # Generate runtime assertion functions
/z-spec:oracle docs/payment.tex            # Property-based testing vs Lean model
/z-spec:refine docs/payment.tex            # Verify code refines spec
/z-spec:elaborate docs/payment.tex         # Add narrative from DESIGN.md
/z-spec:model2code docs/payment.tex swift  # Generate Swift code and tests
/z-spec:audit docs/payment.tex             # Audit test coverage against spec
/z-spec:cleanup                            # Remove tooling files when done
```

### B-Method Workflow (alpha)

The [B-Method](https://en.wikipedia.org/wiki/B-Method) was created by Jean-Raymond Abrial, who also co-created Z. It shares Z's mathematical foundations --- set theory, predicate logic, schemas --- but adds two things Z deliberately omits: a **substitution language** for describing how operations change state (assignments, conditionals, loops), and a **first-class refinement chain** that carries a specification through three stages: Abstract Machine (`.mch`) → Refinement (`.ref`) → Implementation (`.imp`). Each stage is verified against the previous one.

This plugin supports two paths from specification to code:

| | B Refinement | Z + LLM |
|---|---|---|
| **Method** | Deterministic --- proof obligations at each step | Probabilistic --- LLM translates, verification tools check |
| **Guarantee** | Proven correct by construction | Empirical confidence through layered verification |
| **Verification** | Machine-checked proofs (probcli) | Type-checking, model-checking, partition tests, runtime contracts, oracle PBT, abstraction function commutativity |
| **Cost** | Requires writing refinement and gluing invariants | Seconds to generate, but correctness is not proven |

Both paths start from the same place: a formal specification with precise invariants and preconditions. Without a spec, there is no mathematical definition of "correct" to check against. With one, every generated artifact --- code, tests, contracts, proofs --- can be verified against it.

B support is alpha --- the commands work with probcli (no additional tools required) but have not been tested across a wide range of specifications.

```
/z-spec:b-create A user registry with add and remove  # Create B machine
/z-spec:b-check specs/registry.mch                    # Type-check
/z-spec:b-animate specs/registry.mch                  # Animate and model-check
/z-spec:b-refine specs/registry.mch                   # Create refinement machine
/z-spec:b-refine specs/registry.mch specs/registry_r.ref  # Verify refinement
```

Or translate an existing Z spec to B:

```
/z-spec:b-create docs/registry.tex                    # Z-to-B translation
```

<details>
<summary>Reference: ProB compatibility</summary>

The plugin generates specs that work with both fuzz and probcli:

| Issue | Solution |
|-------|----------|
| B keyword conflict | Use `ZBOOL ::= ztrue \| zfalse` |
| Abstract functions | Provide concrete mappings |
| Unbounded integers | Add bounds in invariants |
| Nested schemas | Flatten into single State schema |
| Unbounded inputs | Add upper bounds to inputs |

</details>

<details>
<summary>Reference: spec structure</summary>

Generated specs follow this structure:

1. **Basic Types** --- Given sets (`[USERID, TIMESTAMP]`)
2. **Free Types** --- Enumerations (`Status ::= active | inactive`)
3. **Global Constants** --- Configuration values
4. **State Schemas** --- Entities with invariants
5. **Initialization** --- Valid initial states
6. **Operations** --- State transitions
7. **System Invariants** --- Key properties summary

</details>

## Development

<details>
<summary>Dev/prod namespace isolation</summary>

The working tree uses `name: "z-spec-dev"` in `plugin.json`. The marketplace release uses `name: "z-spec"`. This lets developers run both side by side:

```bash
claude --plugin-dir .
```

| Source | Commands | What they run |
|--------|----------|---------------|
| Marketplace `z-spec` | `/z-spec:check`, `/z-spec:test`, ... | Production prompts |
| Local `z-spec-dev` | `/z-spec-dev:check-dev`, `/z-spec-dev:test-dev`, ... | Working tree prompts |

</details>

<details>
<summary>Release flow</summary>

```bash
# 1. Prepare release (swaps name to prod, removes -dev commands)
bash scripts/release-plugin.sh

# 2. Tag the release
git tag v0.1.0
git push origin v0.1.0

# 3. Restore dev state on main
bash scripts/restore-dev-plugin.sh
git push origin main
```

</details>

<details>
<summary>Project structure</summary>

```
.claude-plugin/
  plugin.json           # Plugin manifest (name: z-spec-dev in working tree)
commands/
  check.md              # /z-spec:check (prod)
  check-dev.md          # /z-spec-dev:check-dev (dev)
  b-check.md            # /z-spec:b-check (prod, B-Method)
  b-check-dev.md        # /z-spec-dev:b-check-dev (dev, B-Method)
  ...                   # One prod + one dev variant per command
scripts/
  release-plugin.sh     # Swap to prod name, remove -dev commands
  restore-dev-plugin.sh # Restore dev state after tagging
reference/
  z-notation.md         # Z notation cheat sheet
  schema-patterns.md    # Common patterns and ProB tips
  probcli-guide.md      # probcli command reference
  b-notation.md         # B-Method notation reference
  b-machine-patterns.md # B machine patterns and Z-to-B translation
templates/
  preamble.tex          # LaTeX preamble for generated specs
```

</details>

## Thanks

- [@ebowman](https://github.com/ebowman) --- `/z-spec:partition`, `/z-spec:prove`, `/z-spec:contracts`, `/z-spec:oracle`, and `/z-spec:refine` commands

## License

MIT License --- see [LICENSE](LICENSE)
