---
description: Install and configure fuzz, probcli, and lean dependencies
argument-hint: "[check|fuzz|probcli|lean|all]"
allowed-tools: Bash(which:*), Bash(uname:*), Bash(fuzz:*), Bash(probcli:*), Bash($PROBCLI:*), Bash(elan:*), Bash(lean:*), Bash(lake:*), Bash(curl:*), Bash(mkdir:*), Bash(tar:*), Bash(unzip:*), Bash(file:*), Bash(test:*), Bash(grep:*), Read, Glob
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

Both platforms follow the same four steps — download the release archive,
**verify it is the archive it claims to be**, unpack it, then **confirm probcli
actually landed** — and both end at `~/Applications/ProB/probcli`, already
executable. Only the archive format differs: a zip on macOS, a gzipped tarball
on Linux.

Neither block assumes how the archive is packed inside. Each reads the archive's
own listing first and picks the extraction directory from it, so that an archive
carrying a top-level `ProB/` and a flat one both put `probcli` at that same
path. Upstream has changed packaging before; a spec toolchain that reports a
successful install and leaves nothing behind is the failure this whole section
exists to prevent, so the layout is checked rather than believed.

#### Choosing a version

Install **1.15.1**, from
`https://stups.hhu-hosting.de/downloads/prob/tcltk/releases/1.15.1/`. Run only
the block for your platform below; each one sets the version and base URL
itself, because every block is a separate shell invocation and nothing assigned
outside it survives.

**Install this version, not the newest one.** ProB 1.16.0 changed the layout of
the coverage census that `-coverage` prints, from a single bracketed line to a
multi-line table, and z-spec reads the bracketed form. On 1.16.x every operation
still fires and the model check still runs, but z-spec reports
`coverage: failed — probcli printed no coverage census` for every specification.
1.15.1 is the newest release whose census z-spec can read.

There is also no `latest` alias to substitute: `releases/current_version.txt` is
stale (it still reports 1.9.3-final, dated 2020) and a `releases/latest/` path
404s. Browse https://stups.hhu-hosting.de/downloads/prob/tcltk/releases/ to see
what exists, but do not move the pin ahead of the parser — that is bead
`z-spec-v0m`, and this whole paragraph goes away when it closes.

#### macOS Installation

One universal archive covers both Intel and Apple Silicon — there is no separate
`aarch64` download.

```bash
PROB_VERSION=1.15.1
PROB_BASE="https://stups.hhu-hosting.de/downloads/prob/tcltk/releases"
PROB_URL="$PROB_BASE/$PROB_VERSION/ProB.macos.zip"
ARCHIVE=~/Applications/ProB.macos.zip

mkdir -p ~/Applications/ProB || {
  echo "ERROR: could not create ~/Applications/ProB" >&2
  exit 1
}

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

# Read the layout out of the archive instead of assuming it: a zip that carries
# its own top-level ProB/ is extracted one level up, a flat one into ProB/
# itself. Either way probcli ends up at ~/Applications/ProB/probcli.
if unzip -Z1 "$ARCHIVE" | grep -q '^ProB/'; then
  DEST=~/Applications
else
  DEST=~/Applications/ProB
fi

# -o overwrites without asking: this is the command you re-run after a failed
# install, and unzip's "replace probcli?" prompt would hang waiting on input.
unzip -oq "$ARCHIVE" -d "$DEST" || {
  echo "ERROR: could not extract $ARCHIVE into $DEST" >&2
  exit 1
}

# A partial or misdirected extract leaves a stale binary answering -version, so
# check the path before trusting it.
test -x ~/Applications/ProB/probcli || {
  echo "ERROR: extracted $ARCHIVE but there is no executable probcli at" >&2
  echo "       ~/Applications/ProB/probcli. The archive layout is not what" >&2
  echo "       this command expects — see 'Common Issues' below." >&2
  exit 1
}

# Verify
~/Applications/ProB/probcli -version || {
  echo "ERROR: ~/Applications/ProB/probcli is installed but would not run." >&2
  echo "       See 'Common Issues' below — missing Tcl/Tk libraries and macOS" >&2
  echo "       quarantine are the usual causes." >&2
  exit 1
}
```

**Full ProB with GUI**: the desktop application, which bundles the GUI and all
dependencies, is linked from https://prob.hhu.de/w/index.php/Download. probcli
alone is enough for `/z-spec:test`.

#### Linux Installation

The Linux release is a gzipped tarball, not a zip.

```bash
PROB_VERSION=1.15.1
PROB_BASE="https://stups.hhu-hosting.de/downloads/prob/tcltk/releases"
PROB_URL="$PROB_BASE/$PROB_VERSION/ProB.linux64.tar.gz"
ARCHIVE=~/Applications/ProB.linux64.tar.gz

mkdir -p ~/Applications/ProB || {
  echo "ERROR: could not create ~/Applications/ProB" >&2
  exit 1
}

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

# Read the layout out of the archive instead of assuming it: a tarball that
# carries its own top-level ProB/ is extracted one level up, a flat one into
# ProB/ itself. Either way probcli ends up at ~/Applications/ProB/probcli.
if tar -tzf "$ARCHIVE" | grep -q '^ProB/'; then
  DEST=~/Applications
else
  DEST=~/Applications/ProB
fi

tar -xzf "$ARCHIVE" -C "$DEST" || {
  echo "ERROR: could not extract $ARCHIVE into $DEST" >&2
  exit 1
}

# A partial or misdirected extract leaves a stale binary answering -version, so
# check the path before trusting it.
test -x ~/Applications/ProB/probcli || {
  echo "ERROR: extracted $ARCHIVE but there is no executable probcli at" >&2
  echo "       ~/Applications/ProB/probcli. The archive layout is not what" >&2
  echo "       this command expects — see 'Common Issues' below." >&2
  exit 1
}

# Verify
~/Applications/ProB/probcli -version || {
  echo "ERROR: ~/Applications/ProB/probcli is installed but would not run." >&2
  echo "       See 'Common Issues' below — missing Tcl/Tk libraries are the" >&2
  echo "       usual cause." >&2
  exit 1
}
```

#### Tcl/Tk Dependency

probcli may need Tcl/Tk libraries even in CLI mode. Install them only if the
verify step above failed with a missing-library error — a working `-version` is
proof you do not need this, and both commands below want a password or a
package-manager lock.

macOS:

```bash
brew install tcl-tk

# Add to shell profile if needed
export PATH="/opt/homebrew/opt/tcl-tk/bin:$PATH"
export LDFLAGS="-L/opt/homebrew/opt/tcl-tk/lib"
export CPPFLAGS="-I/opt/homebrew/opt/tcl-tk/include"
```

Debian/Ubuntu:

```bash
sudo apt-get install tcl tk
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
file ~/Applications/ProB.macos.zip        # macOS
file ~/Applications/ProB.linux64.tar.gz   # Linux
```

"HTML document" means the URL was wrong, not the archive. Confirm the pinned version's directory is still present at https://stups.hhu-hosting.de/downloads/prob/tcltk/releases/ — releases have been withdrawn before. The `-f` flag and the `unzip -tq` / `tar -tzf` checks above exist to make this abort loudly rather than leave a broken install behind.

**`coverage: failed — probcli printed no coverage census`**: you are running ProB 1.16.0 or newer, whose coverage census z-spec cannot read. Confirm with `~/Applications/ProB/probcli -version`, then reinstall 1.15.1 using the block for your platform above. The model check itself is unaffected — only the coverage tier fails — and the reason is under "Choosing a version" above. Tracked as bead `z-spec-v0m`.

**"extracted ... but there is no executable probcli at ~/Applications/ProB/probcli"**: the archive downloaded and unpacked, but upstream repackaged it into a shape the install block does not recognise. List what you actually got and find the binary:

```bash
unzip -Z1 ~/Applications/ProB.macos.zip | head -20        # macOS
tar -tzf ~/Applications/ProB.linux64.tar.gz | head -20    # Linux
```

The install block handles a flat archive and one wrapped in a single top-level `ProB/`; a deeper or differently-named wrapper needs the extracted tree moved so that `probcli` sits directly in `~/Applications/ProB/`. The nine other `/z-spec:*` commands default to that exact path, so leaving the binary where it landed and pointing `$PROBCLI` at it fixes this command and breaks the rest.

**"probcli: cannot execute binary file"**: Wrong platform archive — `ProB.macos.zip` on Linux or `ProB.linux64.tar.gz` on macOS. A single macOS archive serves both Intel and Apple Silicon, so this is never an Intel-vs-arm64 mismatch.

**"Error: PROB_HOME not set"**: Set environment variable:
```bash
export PROB_HOME="$HOME/Applications/ProB"
```

**Quarantine on macOS**: If macOS blocks the binary:
```bash
xattr -d com.apple.quarantine ~/Applications/ProB/probcli
```

### 5. Install Lean 4

Lean 4 is the theorem prover used by `/z-spec:prove` to generate
machine-checked proof obligations from Z specifications. It is optional: fuzz
and probcli cover type-checking and model-checking without it.

#### Install elan (Lean version manager)

```bash
curl https://elan.lean-lang.org/elan-init.sh -sSf | sh
```

This installs `elan`, `lean`, and `lake` (the build system).

After installation, source the environment:

```bash
source "$HOME/.elan/env"
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

Everything is installed; now confirm each tool answers:

```bash
# Test fuzz
mkdir -p .tmp
echo '\begin{zed}[X]\end{zed}' > .tmp/test.tex
fuzz -t .tmp/test.tex

# Test probcli with Z
probcli -version

# Test the Lean toolchain — skip if you did not install it in step 5
elan --version
lean --version
lake --version
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

### 7. Report Results

Summarize what was done and the resulting status. Report only the tools you
actually installed and verified — a row claiming success for a step that was
skipped or that failed is the one thing this command must never print.

The report to emit, verbatim backticks and all:

````text
## Setup Complete

| Tool | Status | Location |
|------|--------|----------|
| fuzz | ✓ Installed | ~/Applications/fuzz/fuzz |
| fuzz.sty | ✓ Installed | /usr/local/texlive/.../fuzz.sty |
| probcli | ✓ Installed | ~/Applications/ProB/probcli |
| elan, lean, lake | ✓ Installed | ~/.elan/bin/ |

## Shell Configuration

Add to ~/.zshrc:

```bash
export PATH="$HOME/Applications/fuzz:$HOME/Applications/ProB:$HOME/.elan/bin:$PATH"
export PROBCLI="$HOME/Applications/ProB/probcli"
```

Run `source ~/.zshrc` or restart your terminal.
````

## Interactive Guidance

If installation fails or user needs help:

1. **Ask about their environment**: macOS version, Intel vs Apple Silicon, existing TeX installation
2. **Diagnose specific errors**: Parse error messages and suggest fixes
3. **Offer alternatives**: If probcli won't install, fuzz alone is still useful for type-checking
4. **Test incrementally**: Verify each step before proceeding

