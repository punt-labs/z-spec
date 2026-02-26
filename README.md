# Z Specification Plugin for Claude Code

Create, validate, and test formal Z specifications for stateful systems using fuzz and ProB.

## Features

- **Guided setup** for fuzz and probcli installation
- **Generate Z specs** from codebase analysis or system descriptions
- **Type-check** with fuzz
- **Animate and model-check** with probcli (ProB)
- **Elaborate** specs with narrative from design documentation
- **Derive test cases** from specs using Test Template Framework (TTF) testing tactics (input partitioning, boundary analysis)
- **ProB-compatible** output (avoids B keyword conflicts, bounded integers, flat schemas)

## Platform Support

**macOS and Linux only.** Windows is not currently supported.

The plugin relies on Unix shell commands and paths. fuzz and probcli are also primarily Unix tools.

## Quick Start

### 1. Install the Plugin

```bash
# Create local marketplace if it doesn't exist
mkdir -p ~/.claude/plugins/local-plugins/.claude-plugin
mkdir -p ~/.claude/plugins/local-plugins/plugins

# Clone this repo
git clone https://github.com/punt-labs/z-spec.git \
    ~/.claude/plugins/local-plugins/plugins/z-spec

# Create marketplace.json
cat > ~/.claude/plugins/local-plugins/.claude-plugin/marketplace.json << 'EOF'
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "local",
  "description": "Local plugins",
  "owner": { "name": "local", "email": "local@example.com" },
  "plugins": [{
    "name": "z-spec",
    "description": "Create, validate, and test formal Z specifications",
    "version": "1.0.0",
    "source": "./plugins/z-spec",
    "category": "development"
  }]
}
EOF

# Register marketplace and install
claude plugin marketplace add ~/.claude/plugins/local-plugins
claude plugin install z-spec@local
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
| `/z setup` | **Start here** — Install and configure fuzz and probcli |
| `/z code2model [focus]` | Create or update a Z specification from codebase or description |
| `/z check [file]` | Type-check a specification with fuzz |
| `/z test [file]` | Validate and animate with probcli |
| `/z partition [spec] [--code [language]] [--operation=NAME] [--json]` | Derive test cases from spec using TTF testing tactics |
| `/z audit [spec] [--json]` | Audit test coverage against spec constraints |
| `/z elaborate [spec] [design]` | Enhance spec with narrative from design docs |
| `/z model2code [spec] [lang]` | Generate code and tests from a Z specification |
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
/z audit docs/payment.tex             # Audit test coverage against spec
/z elaborate docs/payment.tex         # Add narrative from DESIGN.md
```

## Dependencies

The plugin requires two external tools:

### fuzz

The Z type-checker. Compiled from source.
- Repository: https://github.com/Spivoxity/fuzz
- Includes `fuzz.sty` for LaTeX

### probcli

The ProB command-line interface for animation and model-checking.
- Download: https://prob.hhu.de/w/index.php/Download
- Requires Tcl/Tk libraries

**Don't install these manually** - use `/z setup` for guided installation.

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

1. **Basic Types** - Given sets (`[USERID, TIMESTAMP]`)
2. **Free Types** - Enumerations (`Status ::= active | inactive`)
3. **Global Constants** - Configuration values
4. **State Schemas** - Entities with invariants
5. **Initialization** - Valid initial states
6. **Operations** - State transitions
7. **System Invariants** - Key properties summary

## Reference Files

- `reference/z-notation.md` - Z notation cheat sheet
- `reference/schema-patterns.md` - Common patterns and ProB tips
- `reference/probcli-guide.md` - probcli command reference

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

## License

MIT License - see [LICENSE](LICENSE)
