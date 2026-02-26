# Z Specification Plugin for Claude Code

Create, validate, and test formal Z specifications for stateful systems using fuzz and ProB.

## Features

- **Generate Z specs** from codebase analysis or system descriptions (`/z code2model`)
- **Type-check** with fuzz (`/z check`)
- **Animate and model-check** with probcli (`/z test`)
- **Derive test cases** from specs using TTF testing tactics (`/z partition`)
- **Generate code and tests** from specifications (`/z model2code`)
- **Audit test coverage** against spec constraints (`/z audit`)
- **Elaborate** specs with narrative from design documentation (`/z elaborate`)
- **ProB-compatible** output (avoids B keyword conflicts, bounded integers, flat schemas)

## Platform Support

**macOS and Linux only.** Windows is not currently supported.

The plugin relies on Unix shell commands and paths. fuzz and probcli are also primarily Unix tools.

## Quick Start

### 1. Install the Plugin

Install from the Claude Code marketplace:

```bash
claude plugin install z-spec
```

### 2. Install Dependencies

Once the plugin is installed, use the setup command to install fuzz and probcli:

```
/z setup          # Check what's already installed
/z setup all      # Install everything with guided help
```

The setup command will:

- Detect your platform (macOS Intel/Apple Silicon, Linux)
- Check for existing installations
- Guide you through installing fuzz (Z type-checker)
- Guide you through installing probcli (ProB CLI) including Tcl/Tk dependencies
- Verify everything works

### 3. Create Your First Spec

```
/z code2model the user authentication system
```

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

## Dependencies

The plugin requires two external tools:

### fuzz

The Z type-checker. Compiled from source.

- Repository: <https://github.com/Spivoxity/fuzz>
- Includes `fuzz.sty` for LaTeX

### probcli

The ProB command-line interface for animation and model-checking.

- Download: <https://prob.hhu.de/w/index.php/Download>
- Requires Tcl/Tk libraries

**Don't install these manually** — use `/z setup` for guided installation.

## Development

### Dev/Prod Namespace Isolation

The working tree uses `name: "z-spec-dev"` in `plugin.json`. The marketplace release uses `name: "z-spec"`. This lets developers run both side by side:

```bash
# Load the local dev plugin alongside the marketplace version
claude --plugin-dir .
```

| Source | Commands | What they run |
|--------|----------|---------------|
| Marketplace `z-spec` | `/z check`, `/z test`, ... | Production prompts |
| Local `z-spec-dev` | `/z-dev check-dev`, `/z-dev test-dev`, ... | Working tree prompts |

### Release Flow

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

### Project Structure

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

## ProB Compatibility

The plugin generates specs that work with both fuzz and probcli:

| Issue | Solution |
|-------|----------|
| B keyword conflict | Use `ZBOOL ::= ztrue \| zfalse` |
| Abstract functions | Provide concrete mappings |
| Unbounded integers | Add bounds in invariants |
| Nested schemas | Flatten into single State schema |
| Unbounded inputs | Add upper bounds to inputs |

## Specification Structure

Generated specs follow this structure:

1. **Basic Types** — Given sets (`[USERID, TIMESTAMP]`)
2. **Free Types** — Enumerations (`Status ::= active | inactive`)
3. **Global Constants** — Configuration values
4. **State Schemas** — Entities with invariants
5. **Initialization** — Valid initial states
6. **Operations** — State transitions
7. **System Invariants** — Key properties summary

## Example Output

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

## Test Case Derivation (`/z partition`)

`/z partition` applies the [Test Template Framework](https://doi.org/10.1007/3-540-48257-1_11) (TTF) to derive conformance test cases directly from the mathematics of your Z operations. Rather than writing tests by intuition, the spec's structure determines what must be tested.

The command applies three tactics:

1. **DNF decomposition** — operations with disjunctions (`\lor`) or conditionals encode multiple behaviors. Each disjunct becomes a separate behavioral branch requiring independent testing.
2. **Standard partitions** — type-based equivalence classes for each input and state variable (e.g., bounded `\nat` yields endpoint and midpoint values; free types yield every constructor).
3. **Boundary analysis** — values at and around each constraint edge, catching off-by-one errors in the implementation.

For the `AdvanceLevel` example above, this produces:

| # | Class | Inputs | Pre-state | Expected |
|---|-------|--------|-----------|----------|
| 1 | Happy path | accuracy=95 | level=5 | level'=6 |
| 2 | Boundary: min accuracy | accuracy=90 | level=5 | level'=6 |
| 3 | Boundary: max level | accuracy=95 | level=25 | level'=26 |
| 4 | Rejected: low accuracy | accuracy=89 | level=5 | no change |
| 5 | Rejected: at max | accuracy=95 | level=26 | no change |

Add `--code swift` (or python, typescript, kotlin) to generate executable test cases from the partition table.

## License

MIT License — see [LICENSE](LICENSE)
