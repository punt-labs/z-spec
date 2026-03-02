---
description: Install and configure fuzz, probcli, and lean dependencies
argument-hint: "[check|fuzz|probcli|lean|all]"
allowed-tools: Bash(which:*), Bash(uname:*), Bash(fuzz:*), Bash(probcli:*), Bash($PROBCLI:*), Bash(elan:*), Bash(lean:*), Bash(lake:*), Bash(curl:*), Read, Glob
---

# Setup Z Specification Tools

You are helping the user install and configure the tools needed for Z specification development.

## Input

Arguments: $ARGUMENTS

Parse as:

- `check` - Check what's installed and report status
- `fuzz` - Install fuzz type-checker
- `probcli` - Install ProB command-line interface
- `lean` - Install Lean 4 theorem prover (elan + lean + lake)
- `all` - Install fuzz, probcli, and lean
- (no argument) - Same as `check`

**Note**: TeX files (fuzz.sty, *.mf) are automatically copied to your project's `docs/` directory when you run `/z-spec:create`, `/z-spec:check`, or `/z-spec:test`. Use `/z-spec:cleanup` to remove them.

## Process

### 1. Detect Platform

```bash
uname -s  # Darwin, Linux, etc.
uname -m  # arm64, x86_64, etc.
```

### 2. Check Current Status

Always start by checking what's already installed:

```bash
# Check fuzz
which fuzz && fuzz -version

# Check probcli
which probcli || test -x "$HOME/Applications/ProB/probcli" && echo "probcli found"

# Check fuzz.sty in TeX path
kpsewhich fuzz.sty

# Check Tcl/Tk (needed for probcli on some systems)
which wish || brew list tcl-tk 2>/dev/null

# Check Lean 4 (optional, for /z-spec:prove)
which elan && elan --version
which lean && lean --version
which lake && lake --version
```

Report status clearly:

```text
## Current Status

| Tool | Status |
|------|--------|
| fuzz | ✓ Installed (version X) |
| fuzz.sty | ✓ Found in TeX path |
| probcli | ✗ Not found |
| Tcl/Tk | ✓ Available |
| elan | ✓ Installed (version X) |
| lean | ✓ Installed (version X) |
| lake | ✓ Installed (version X) |
```

### 3. Install fuzz

fuzz is the Z type-checker. It must be compiled from source.

#### Prerequisites

**macOS:**
```bash
# Xcode command line tools (for gcc/make)
xcode-select --install

# TeX distribution (for fuzz.sty installation)
# User should have MacTeX or BasicTeX installed
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get install build-essential texlive-base
```

#### Installation Steps

```bash
# Clone fuzz repository
cd ~/Applications  # or user's preferred location
git clone https://github.com/Spivoxity/fuzz.git
cd fuzz

# Build
make

# Install fuzz.sty to TeX path (may need sudo)
sudo make install

# Verify
fuzz -version
kpsewhich fuzz.sty
```

#### Add to PATH

If `fuzz` isn't in PATH after building:

```bash
# Add to shell profile (~/.zshrc or ~/.bashrc)
export PATH="$HOME/Applications/fuzz:$PATH"
```

#### Common Issues

**"fuzz.sty not found"**: Run `sudo make install` in the fuzz directory, then `sudo texhash`.

**"make: gcc: command not found"**: Install Xcode command line tools: `xcode-select --install`

### 4. Install probcli

probcli is the ProB command-line interface for animating and model-checking Z specifications.

#### macOS Installation

**Option A: Standalone CLI (Recommended)**

```bash
# Create directory
mkdir -p ~/Applications/ProB
cd ~/Applications/ProB

# Download latest release
# Check https://prob.hhu.de/w/index.php/Download for current version
curl -L -o probcli.zip "https://prob.hhu.de/downloads/prob2-latest/prob-macOS.zip"

# Or for Apple Silicon specifically:
# curl -L -o probcli.zip "https://prob.hhu.de/downloads/prob2-latest/prob-macOS-aarch64.zip"

unzip probcli.zip
chmod +x probcli

# Verify
./probcli -version
```

**Option B: Full ProB Installation**

Download the full ProB application from https://prob.hhu.de/w/index.php/Download which includes the GUI and all dependencies.

#### Tcl/Tk Dependency

probcli may require Tcl/Tk libraries even in CLI mode. On macOS:

```bash
# Install via Homebrew
brew install tcl-tk

# Add to shell profile if needed
export PATH="/opt/homebrew/opt/tcl-tk/bin:$PATH"
export LDFLAGS="-L/opt/homebrew/opt/tcl-tk/lib"
export CPPFLAGS="-I/opt/homebrew/opt/tcl-tk/include"
```

#### Add to PATH

```bash
# Add to shell profile (~/.zshrc or ~/.bashrc)
export PROBCLI="$HOME/Applications/ProB/probcli"
export PATH="$HOME/Applications/ProB:$PATH"
```

Or create a symlink:
```bash
sudo ln -s ~/Applications/ProB/probcli /usr/local/bin/probcli
```

#### Linux Installation

```bash
# Download
mkdir -p ~/Applications/ProB
cd ~/Applications/ProB
curl -L -o probcli.zip "https://prob.hhu.de/downloads/prob2-latest/prob-linux64.zip"
unzip probcli.zip
chmod +x probcli

# Install Tcl/Tk if needed
sudo apt-get install tcl tk

# Verify
./probcli -version
```

#### Common Issues

**"dyld: Library not loaded: libtcl"**: Install Tcl/Tk via Homebrew: `brew install tcl-tk`

**"probcli: cannot execute binary file"**: Wrong architecture. Download the correct version (Intel vs Apple Silicon).

**"Error: PROB_HOME not set"**: Set environment variable:
```bash
export PROB_HOME="$HOME/Applications/ProB"
```

**Quarantine on macOS**: If macOS blocks the binary:
```bash
xattr -d com.apple.quarantine ~/Applications/ProB/probcli
```

### 5. Verify Installation

After installation, verify everything works:

```bash
# Test fuzz
echo '\begin{zed}[X]\end{zed}' > /tmp/test.tex
fuzz -t /tmp/test.tex

# Test probcli with Z
probcli -version
```

Create a simple test spec and run both tools:

```bash
cat > /tmp/test_spec.tex << 'EOF'
\documentclass{article}
\usepackage{fuzz}
\begin{document}
\begin{zed}
[ID]
\end{zed}
\begin{zed}
ZBOOL ::= ztrue | zfalse
\end{zed}
\begin{schema}{State}
count : \nat
\where
count \leq 100
\end{schema}
\begin{schema}{Init}
State'
\where
count' = 0
\end{schema}
\end{document}
EOF

fuzz -t /tmp/test_spec.tex && echo "fuzz: OK"
probcli /tmp/test_spec.tex -init && echo "probcli: OK"
```

Test probcli with a B machine:

```bash
cat > /tmp/test_machine.mch << 'EOF'
MACHINE TestMachine
VARIABLES count
INVARIANT count : NAT & count <= 100
INITIALISATION count := 0
OPERATIONS
    increment = PRE count < 100 THEN count := count + 1 END
END
EOF

probcli /tmp/test_machine.mch -init && echo "probcli B: OK"
```

**Note**: probcli handles both Z specifications (`.tex`) and B machines (`.mch`, `.ref`, `.imp`). No additional tools are needed for B-Method work.

### 6. Report Results

Summarize what was done and current status:

```
## Setup Complete

| Tool | Status | Location |
|------|--------|----------|
| fuzz | ✓ Installed | ~/Applications/fuzz/fuzz |
| fuzz.sty | ✓ Installed | /usr/local/texlive/.../fuzz.sty |
| probcli | ✓ Installed | ~/Applications/ProB/probcli |

## Shell Configuration

Add to ~/.zshrc:
```bash
export PATH="$HOME/Applications/fuzz:$HOME/Applications/ProB:$PATH"
export PROBCLI="$HOME/Applications/ProB/probcli"
```

Run `source ~/.zshrc` or restart your terminal.
```

### 5. Install Lean 4

Lean 4 is the theorem prover used by `/z-spec:prove` to generate
machine-checked proof obligations from Z specifications.

#### Install elan (Lean version manager)

```bash
curl https://elan.lean-lang.org/elan-init.sh -sSf | sh
```

This installs `elan`, `lean`, and `lake` (the build system).

After installation, source the environment:

```bash
source "$HOME/.elan/env"
```

#### Verify

```bash
elan --version
lean --version
lake --version
```

#### Add to PATH

If `lean` isn't in PATH after installing elan:

```bash
# Add to shell profile (~/.zshrc or ~/.bashrc)
export PATH="$HOME/.elan/bin:$PATH"
```

#### Common Issues

**"elan: command not found" after install**: Run `source "$HOME/.elan/env"` or restart your terminal.

**Slow first build**: The first `lake build` in a Mathlib project downloads precompiled dependencies (~2 GB). Run `lake exe cache get` first to fetch the cache.

**"no toolchain installed"**: Run `elan default leanprover/lean4:stable` to set the default toolchain.

### 6. Verify Installation

After installation, verify everything works:

```bash
# Test fuzz
echo '\begin{zed}[X]\end{zed}' > /tmp/test.tex
fuzz -t /tmp/test.tex

# Test probcli
probcli -version

# Test lean (if installed)
lean --version && lake --version
```

## Interactive Guidance

If installation fails or user needs help:

1. **Ask about their environment**: macOS version, Intel vs Apple Silicon, existing TeX installation
2. **Diagnose specific errors**: Parse error messages and suggest fixes
3. **Offer alternatives**: If probcli won't install, fuzz alone is still useful for type-checking
4. **Test incrementally**: Verify each step before proceeding

