---
description: Install and configure fuzz, probcli, and lean dependencies
argument-hint: "[check|fuzz|probcli|lean|all]"
allowed-tools: Bash(which:*), Bash(uname:*), Bash(fuzz:*), Bash(probcli:*), Bash($PROBCLI:*), Bash(elan:*), Bash(lean:*), Bash(lake:*), Bash(curl:*), Bash(mkdir:*), Bash(mktemp:*), Bash(tar:*), Bash(unzip:*), Bash(file:*), Read, Glob
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

Both platforms follow the same three steps — download the release archive,
**verify it is the archive it claims to be**, then unpack it — and both end at
`~/Applications/ProB/probcli`, already executable. Only the unpack command
differs: the Linux tarball carries a top-level `ProB/` directory, the macOS zip
does not, so the zip is unpacked into that directory explicitly.

#### Choosing a version

```bash
PROB_VERSION=1.15.1
PROB_BASE="https://stups.hhu-hosting.de/downloads/prob/tcltk/releases"
```

**Install this version, not the newest one.** ProB 1.16.0 changed the layout of
the coverage census that `-coverage` prints, from a single bracketed line to a
multi-line table, and z-spec reads the bracketed form. On 1.16.x every operation
still fires and the model check still runs, but z-spec reports
`coverage: failed — probcli printed no coverage census` for every specification.
1.15.1 is the newest release whose census z-spec can read.

There is also no `latest` alias to substitute: `releases/current_version.txt` is
stale (it still reports 1.9.3-final, dated 2020) and a `releases/latest/` path
404s. Browse https://stups.hhu-hosting.de/downloads/prob/tcltk/releases/ to see
what exists, but do not move the pin ahead of the parser.

#### macOS Installation

One universal archive covers both Intel and Apple Silicon — there is no separate
`aarch64` download.

```bash
PROB_URL="$PROB_BASE/$PROB_VERSION/ProB.macos.zip"
ARCHIVE="$(mktemp -d)/ProB.macos.zip"
mkdir -p ~/Applications/ProB

# -f makes curl exit nonzero on 404/5xx instead of saving the error page as
# if it were the archive.
curl -fL -o "$ARCHIVE" "$PROB_URL" || {
  echo "ERROR: download failed: $PROB_URL" >&2
  exit 1
}

# Refuse to extract anything that is not actually a zip.
unzip -tq "$ARCHIVE" || {
  echo "ERROR: $PROB_URL did not return a zip archive (got: $(file -b "$ARCHIVE"))" >&2
  exit 1
}

# The macOS zip is packed flat, so name the destination directory.
unzip -q "$ARCHIVE" -d ~/Applications/ProB

# Verify
~/Applications/ProB/probcli -version
```

**Full ProB with GUI**: the desktop application, which bundles the GUI and all
dependencies, is linked from https://prob.hhu.de/w/index.php/Download. probcli
alone is enough for `/z-spec:test`.

#### Linux Installation

The Linux release is a gzipped tarball, not a zip.

```bash
PROB_URL="$PROB_BASE/$PROB_VERSION/ProB.linux64.tar.gz"
ARCHIVE="$(mktemp -d)/ProB.linux64.tar.gz"
mkdir -p ~/Applications

# -f makes curl exit nonzero on 404/5xx instead of saving the error page as
# if it were the archive.
curl -fL -o "$ARCHIVE" "$PROB_URL" || {
  echo "ERROR: download failed: $PROB_URL" >&2
  exit 1
}

# Refuse to extract anything that is not actually a gzip tarball.
tar -tzf "$ARCHIVE" > /dev/null || {
  echo "ERROR: $PROB_URL did not return a gzip tarball (got: $(file -b "$ARCHIVE"))" >&2
  exit 1
}

tar -xzf "$ARCHIVE" -C ~/Applications   # creates ~/Applications/ProB/

# Install Tcl/Tk if needed
sudo apt-get install tcl tk

# Verify
~/Applications/ProB/probcli -version
```

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

#### Common Issues

**"dyld: Library not loaded: libtcl"**: Install Tcl/Tk via Homebrew: `brew install tcl-tk`

**Setup reported success but `probcli` is missing, or the archive is a few hundred bytes**: the download returned an HTTP error page and it was saved under the archive's name. `curl -L -o` without `-f` exits 0 on a 404, so the error body lands on disk looking like a download that worked, and `z-spec doctor` later reports `probcli: NOT FOUND` with nothing pointing back at the cause. Check what you actually got:

```bash
file "$ARCHIVE"   # "HTML document" means the URL is wrong, not the archive
```

Then confirm the pinned version's directory is still present at https://stups.hhu-hosting.de/downloads/prob/tcltk/releases/ — releases have been withdrawn before. The `-f` flag and the `unzip -tq` / `tar -tzf` checks above exist to make this abort loudly rather than leave a broken install behind.

**"probcli: cannot execute binary file"**: Wrong platform archive — `ProB.macos.zip` on Linux or `ProB.linux64.tar.gz` on macOS. A single macOS archive serves both Intel and Apple Silicon, so this is never an Intel-vs-arm64 mismatch.

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
mkdir -p .tmp
echo '\begin{zed}[X]\end{zed}' > .tmp/test.tex
fuzz -t .tmp/test.tex

# Test probcli with Z
probcli -version
```

Create a simple test spec and run both tools:

```bash
mkdir -p .tmp
cat > .tmp/test_spec.tex << 'EOF'
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

fuzz -t .tmp/test_spec.tex && echo "fuzz: OK"
probcli .tmp/test_spec.tex -init && echo "probcli: OK"
```

Test probcli with a B machine:

```bash
mkdir -p .tmp
cat > .tmp/test_machine.mch << 'EOF'
MACHINE TestMachine
VARIABLES count
INVARIANT count : NAT & count <= 100
INITIALISATION count := 0
OPERATIONS
    increment = PRE count < 100 THEN count := count + 1 END
END
EOF

probcli .tmp/test_machine.mch -init && echo "probcli B: OK"
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
mkdir -p .tmp
echo '\begin{zed}[X]\end{zed}' > .tmp/test.tex
fuzz -t .tmp/test.tex

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

