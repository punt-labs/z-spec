# Z Specification Plugin for Claude Code

> Formal specifications that type-check, animate, and generate tests --- from English to math to code.

[![License](https://img.shields.io/github/license/punt-labs/z-spec)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/punt-labs/z-spec/docs.yml?label=CI)](https://github.com/punt-labs/z-spec/actions/workflows/docs.yml)

**Platforms:** macOS, Linux

## Quick Start

First, add the Punt Labs marketplace (one-time):

```bash
claude plugin marketplace add punt-labs/claude-plugins
```

Then install the plugin:

```bash
claude plugin install z-spec
```

Inside Claude Code:

```
/z setup all                              # Install fuzz and probcli
/z code2model the user authentication system   # Generate your first spec
/z check docs/auth.tex                    # Type-check it
/z test docs/auth.tex                     # Animate and model-check
```

<details>
<summary>What /z setup installs</summary>

- **fuzz** --- Z type-checker ([source](https://github.com/Spivoxity/fuzz)), includes `fuzz.sty` for LaTeX
- **probcli** --- ProB CLI for animation and model-checking ([download](https://prob.hhu.de/w/index.php/Download)), requires Tcl/Tk

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

`/z partition` applies the [Test Template Framework](https://doi.org/10.1007/3-540-48257-1_11) (TTF) to derive conformance test cases directly from the spec's mathematics:

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

- **Generate Z specs** from codebase analysis or system descriptions (`/z code2model`)
- **Type-check** with fuzz (`/z check`)
- **Animate and model-check** with probcli (`/z test`)
- **Derive test cases** from specs using TTF testing tactics (`/z partition`)
- **Generate code and tests** from specifications (`/z model2code`)
- **Audit test coverage** against spec constraints (`/z audit`)
- **Elaborate** specs with narrative from design documentation (`/z elaborate`)
- **ProB-compatible** output (avoids B keyword conflicts, bounded integers, flat schemas)

## Commands

| Command | Description |
|---------|-------------|
| `/z setup [check\|fuzz\|probcli\|all]` | Install and configure fuzz and probcli |
| `/z code2model [focus]` | Create or update a Z specification from codebase or description |
| `/z check [file]` | Type-check a specification with fuzz |
| `/z test [file] [-v] [-a N] [-s N]` | Validate and animate with probcli |
| `/z partition [spec] [--code [language]] [--operation=NAME] [--json]` | Derive test cases from spec using TTF testing tactics |
| `/z model2code [spec] [language]` | Generate code and tests from a Z specification |
| `/z audit [spec] [--json] [--test-dir=DIR]` | Audit test coverage against spec constraints |
| `/z elaborate [spec] [design]` | Enhance spec with narrative from design docs |
| `/z cleanup [dir]` | Remove TeX tooling files (keeps .tex and .pdf) |
| `/z help` | Show quick reference |

## Workflow

```
/z setup                              # Install tools (first time only)
/z code2model the payment system      # Generate spec from codebase
/z check docs/payment.tex             # Type-check
/z test docs/payment.tex              # Animate and model-check
/z partition docs/payment.tex         # Derive test cases from spec
/z partition docs/payment.tex --code  # Generate executable test code
/z elaborate docs/payment.tex         # Add narrative from DESIGN.md
/z model2code docs/payment.tex swift  # Generate Swift code and tests
/z audit docs/payment.tex             # Audit test coverage against spec
/z cleanup                            # Remove tooling files when done
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
| Marketplace `z-spec` | `/z check`, `/z test`, ... | Production prompts |
| Local `z-spec-dev` | `/z-dev check-dev`, `/z-dev test-dev`, ... | Working tree prompts |

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
  check.md              # /z check (prod)
  check-dev.md          # /z-dev check-dev (dev)
  ...                   # One prod + one dev variant per command
scripts/
  release-plugin.sh     # Swap to prod name, remove -dev commands
  restore-dev-plugin.sh # Restore dev state after tagging
reference/
  z-notation.md         # Z notation cheat sheet
  schema-patterns.md    # Common patterns and ProB tips
  probcli-guide.md      # probcli command reference
templates/
  preamble.tex          # LaTeX preamble for generated specs
```

</details>

## Thanks

- [@ebowman](https://github.com/ebowman) --- `/z partition` command, bringing TTF testing tactics to Z specs

## License

MIT License --- see [LICENSE](LICENSE)
