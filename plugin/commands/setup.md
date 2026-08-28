---
description: Install and configure fuzz, probcli, and lean dependencies
argument-hint: "[check|fuzz|probcli|lean|all]"
allowed-tools: Bash(uname:*), Bash(fuzz:*), Bash(probcli:*), Bash($PROBCLI:*), Bash($PROBCLI_BIN:*), Bash($FUZZ:*), Bash($FUZZ_BIN:*), Bash($lean_tool:*), Bash($LEAN_BIN:*), Bash(elan:*), Bash(lean:*), Bash(lake:*), Bash(curl:*), Bash(mkdir:*), Bash(tar:*), Bash(unzip:*), Bash(file:*), Bash(test:*), Bash(grep:*), Bash(kpsewhich:*), Bash(brew:*), Bash(cat:*), Bash(xattr:*), Bash(~/Applications/ProB/probcli:*), Bash(~/elan-init.sh:*), Bash(chmod:*), Bash(command:*), Bash(head:*), Read, Glob
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
# Check fuzz. $FUZZ wins, then PATH — the order resolve_fuzz() uses. Note
# there is no conventional-path fallback for fuzz: a binary sitting in
# ~/Applications/fuzz that is neither on PATH nor named by $FUZZ is a binary
# the engine will not find, however well it runs when you type its full path.
if [ -n "${FUZZ:-}" ] && [ -f "$FUZZ" ]; then
  FUZZ_BIN="$FUZZ"
else
  FUZZ_BIN="$(command -v fuzz 2>/dev/null)"
fi

if test -x "$FUZZ_BIN"; then
  echo "fuzz: $FUZZ_BIN"
  "$FUZZ_BIN" -version
elif test -e "$FUZZ_BIN"; then
  echo "fuzz: NOT EXECUTABLE at $FUZZ_BIN"
else
  echo "fuzz: NOT FOUND (not on PATH, and \$FUZZ does not name it)"
fi

# Check probcli, and report which version. Presence alone is not enough: a
# 1.16.x install answers every check in this section and still fails the
# coverage tier of every specification, so a bare "found" here would send the
# user off to discover that one command later with nothing pointing back.
# $PROBCLI wins, then PATH, then the conventional path — the order
# resolve_probcli() uses. Resolving any other way would make this report
# describe a binary the other commands are not going to run, which is the
# whole failure this section exists to prevent.
if [ -n "${PROBCLI:-}" ] && [ -f "$PROBCLI" ]; then
  PROBCLI_BIN="$PROBCLI"
else
  PROBCLI_BIN="$(command -v probcli 2>/dev/null || echo "$HOME/Applications/ProB/probcli")"
fi

if test -x "$PROBCLI_BIN"; then
  PROB_VER="$("$PROBCLI_BIN" -version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
  echo "probcli: $PROBCLI_BIN (version ${PROB_VER:-unreadable})"
  test "$PROB_VER" = "1.15.1" || echo "  WARNING: z-spec needs 1.15.1 — see 'Choosing a version' below"
elif test -e "$PROBCLI_BIN"; then
  echo "probcli: NOT EXECUTABLE at $PROBCLI_BIN"
else
  echo "probcli: NOT FOUND"
fi

# Check fuzz.sty in the TeX path. kpsewhich prints nothing and exits nonzero
# when it finds nothing, which is silence where a status line belongs.
if FUZZ_STY="$(kpsewhich fuzz.sty 2>/dev/null)" && [ -n "$FUZZ_STY" ]; then
  echo "fuzz.sty: $FUZZ_STY"
else
  echo "fuzz.sty: NOT FOUND in the TeX path"
fi

# Check Tcl/Tk. probcli needs it on some systems and not others, so absence
# here is a note, not a verdict — the probcli line above is the real test.
if command -v wish >/dev/null 2>&1; then
  echo "tcl/tk: $(command -v wish)"
else
  echo "tcl/tk: no wish on PATH (only matters if probcli reports a missing library)"
fi

# Check the Lean toolchain (optional, for /z-spec:prove). Three states, the
# same three section 6 reports: on PATH, present under ~/.elan/bin but not on
# PATH, or absent. /z-spec:prove looks on PATH and nowhere else, so the middle
# state is a real distinction and not a formality.
for lean_tool in elan lean lake; do
  if command -v "$lean_tool" >/dev/null 2>&1; then
    echo "$lean_tool: $(command -v "$lean_tool")"
    "$lean_tool" --version
  elif [ -x ~/.elan/bin/"$lean_tool" ]; then
    echo "$lean_tool: at ~/.elan/bin but NOT on PATH — /z-spec:prove will not see it"
  else
    echo "$lean_tool: NOT FOUND (optional)"
  fi
done
```

Report status clearly, and give probcli's version rather than a bare tick — an
installed-but-unusable version is the one status a reader must not have to
infer:

```text
## Current Status

| Tool | Status |
|------|--------|
| fuzz | ✓ Installed (version X) |
| fuzz.sty | ✓ Found in TeX path |
| probcli | ⚠ Installed 1.16.0 — z-spec needs 1.15.1 |
| Tcl/Tk | ✓ Available |
| elan | ✓ Installed (version X) |
| lean | ✓ Installed (version X) |
| lake | ✓ Installed (version X) |
```

probcli has three states to distinguish, not two: absent, installed at 1.15.1,
and installed at some other version. The third reads as success everywhere
except the coverage tier, so name it here and point at "Choosing a version"
below.

### 3. Install fuzz

fuzz is the Z type-checker. It must be compiled from source.

#### Prerequisites

**macOS** — yours to run; `xcode-select` opens a GUI installer and is not among
this command's tools:

```text
# Xcode command line tools (for gcc/make)
xcode-select --install

# TeX distribution (for fuzz.sty installation)
# User should have MacTeX or BasicTeX installed
```

**Linux (Debian/Ubuntu):** run this yourself, for the same reason:

```text
sudo apt-get install build-essential texlive-base
```

#### Installation Steps

Building fuzz is a human procedure from end to end — `git`, `make` and `sudo`
are all outside this command's tools — so the block below is what to type, not
something the agent will run for you.

```text
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

# Check the tools first. Without this, a missing unzip exits 127 and gets
# reported below as "did not return a zip archive" — a bad diagnosis of a
# problem that has nothing to do with the download.
for tool in curl unzip file; do
  command -v "$tool" >/dev/null || {
    echo "ERROR: $tool is not installed, and this block needs it" >&2
    exit 1
  }
done

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
# Capture the listing first: piped straight into grep, a failure of unzip
# itself would be invisible and the empty output would read as "flat".
LISTING="$(unzip -Z1 "$ARCHIVE")" || {
  echo "ERROR: could not list the contents of $ARCHIVE" >&2
  exit 1
}

if printf '%s\n' "$LISTING" | grep -q '^ProB/'; then
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

# Do not trust the archive's exec bit — this repo's own CI chmods the binary
# after unpacking the same release.
CHMOD_ERR="$(chmod +x ~/Applications/ProB/probcli 2>&1)"

# A partial or misdirected extract leaves a stale binary answering -version, so
# check the path before trusting it. Whether the file exists is what separates
# the two causes: absent means the archive unpacked into a shape this block
# does not know, present-but-not-executable means chmod was refused, and
# reporting either as the other sends the reader after the wrong problem.
test -x ~/Applications/ProB/probcli || {
  if [ -e ~/Applications/ProB/probcli ]; then
    echo "ERROR: probcli is at ~/Applications/ProB/probcli but could not be" >&2
    echo "       made executable: ${CHMOD_ERR:-chmod reported no reason}" >&2
  else
    echo "ERROR: extracted $ARCHIVE but there is no probcli at" >&2
    echo "       ~/Applications/ProB/probcli. The archive layout is not what" >&2
    echo "       this command expects — see 'Common Issues' below." >&2
  fi
  exit 1
}

# Verify. Two distinct failures: it will not run, or it runs and is the wrong
# version — the second is what you get when an older install is still in place,
# and it passes every check above.
PROB_OUT="$(~/Applications/ProB/probcli -version 2>&1)" || {
  echo "ERROR: ~/Applications/ProB/probcli is installed but would not run:" >&2
  printf '%s\n' "$PROB_OUT" >&2
  echo "       See 'Common Issues' below — missing Tcl/Tk libraries and macOS" >&2
  echo "       quarantine are the usual causes." >&2
  exit 1
}

# Extract the version and compare it exactly. A substring match for "1.15.1"
# would also accept a future 1.15.10, and accepting the wrong version silently
# is the failure this block is here to stop.
PROB_VER="$(printf '%s\n' "$PROB_OUT" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"

test "$PROB_VER" = "1.15.1" || {
  echo "ERROR: expected ProB 1.15.1 at ~/Applications/ProB/probcli, but got:" >&2
  printf '%s\n' "$PROB_OUT" >&2
  echo "       An earlier install is still there. See 'Choosing a version'." >&2
  exit 1
}

printf '%s\n' "$PROB_OUT"
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

# Check the tools first. Without this, a missing tar exits 127 and gets
# reported below as "did not return a gzip tarball" — a bad diagnosis of a
# problem that has nothing to do with the download.
for tool in curl tar file; do
  command -v "$tool" >/dev/null || {
    echo "ERROR: $tool is not installed, and this block needs it" >&2
    exit 1
  }
done

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

# One command does two jobs here: listing the tarball proves it really is a
# gzip tarball, and the listing is what the layout check reads. Capture it
# rather than piping into grep, so a failure of tar itself is not mistaken for
# an archive with no top-level ProB/.
LISTING="$(tar -tzf "$ARCHIVE")" || {
  echo "ERROR: $PROB_URL did not return a gzip tarball (got: $(file -b "$ARCHIVE"))" >&2
  exit 1
}

# Read the layout out of the archive instead of assuming it: a tarball that
# carries its own top-level ProB/ is extracted one level up, a flat one into
# ProB/ itself. Either way probcli ends up at ~/Applications/ProB/probcli.
if printf '%s\n' "$LISTING" | grep -q '^ProB/'; then
  DEST=~/Applications
else
  DEST=~/Applications/ProB
fi

tar -xzf "$ARCHIVE" -C "$DEST" || {
  echo "ERROR: could not extract $ARCHIVE into $DEST" >&2
  exit 1
}

# Do not trust the archive's exec bit — this repo's own CI chmods the binary
# after unpacking this very tarball.
CHMOD_ERR="$(chmod +x ~/Applications/ProB/probcli 2>&1)"

# A partial or misdirected extract leaves a stale binary answering -version, so
# check the path before trusting it. Whether the file exists is what separates
# the two causes: absent means the archive unpacked into a shape this block
# does not know, present-but-not-executable means chmod was refused, and
# reporting either as the other sends the reader after the wrong problem.
test -x ~/Applications/ProB/probcli || {
  if [ -e ~/Applications/ProB/probcli ]; then
    echo "ERROR: probcli is at ~/Applications/ProB/probcli but could not be" >&2
    echo "       made executable: ${CHMOD_ERR:-chmod reported no reason}" >&2
  else
    echo "ERROR: extracted $ARCHIVE but there is no probcli at" >&2
    echo "       ~/Applications/ProB/probcli. The archive layout is not what" >&2
    echo "       this command expects — see 'Common Issues' below." >&2
  fi
  exit 1
}

# Verify. Two distinct failures: it will not run, or it runs and is the wrong
# version — the second is what you get when an older install is still in place,
# and it passes every check above.
PROB_OUT="$(~/Applications/ProB/probcli -version 2>&1)" || {
  echo "ERROR: ~/Applications/ProB/probcli is installed but would not run:" >&2
  printf '%s\n' "$PROB_OUT" >&2
  echo "       See 'Common Issues' below — missing Tcl/Tk libraries are the" >&2
  echo "       usual cause." >&2
  exit 1
}

# Extract the version and compare it exactly. A substring match for "1.15.1"
# would also accept a future 1.15.10, and accepting the wrong version silently
# is the failure this block is here to stop.
PROB_VER="$(printf '%s\n' "$PROB_OUT" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"

test "$PROB_VER" = "1.15.1" || {
  echo "ERROR: expected ProB 1.15.1 at ~/Applications/ProB/probcli, but got:" >&2
  printf '%s\n' "$PROB_OUT" >&2
  echo "       An earlier install is still there. See 'Choosing a version'." >&2
  exit 1
}

printf '%s\n' "$PROB_OUT"
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

Debian/Ubuntu — run this yourself; it needs a password, and `sudo` is
deliberately not among this command's tools:

```text
sudo apt-get install tcl tk
```

#### Add to PATH

```bash
# Add to shell profile (~/.zshrc or ~/.bashrc)
export PROBCLI="$HOME/Applications/ProB/probcli"
export PATH="$HOME/Applications/ProB:$PATH"
```

Or create a symlink — again yours to run, not the agent's:

```text
sudo ln -s ~/Applications/ProB/probcli /usr/local/bin/probcli
```

#### Common Issues

**"dyld: Library not loaded: libtcl"**: Install Tcl/Tk via Homebrew: `brew install tcl-tk`

**Setup reported success but `probcli` is missing, or the archive is a few hundred bytes**: the download returned an HTTP error page and it was saved under the archive's name. `curl -L -o` without `-f` exits 0 on a 404, so the error body lands on disk looking like a download that worked, and `z-spec doctor` later reports `probcli: NOT FOUND` with nothing pointing back at the cause. Check what you actually got:

```bash
file ~/Applications/ProB.macos.zip        # macOS
file ~/Applications/ProB.linux64.tar.gz   # Linux
```

"HTML document" means the URL was wrong, not the archive. Confirm the pinned version's directory is still present at https://stups.hhu-hosting.de/downloads/prob/tcltk/releases/ — releases have been withdrawn before. The `-f` flag, the `unzip -tq` / `tar -tzf` type checks, and the `test -x` check after extraction all exist to make this abort loudly rather than leave a broken install behind. None of them can be dropped: `-f` catches the error page, the type check catches a file that is not the archive it is named after, and `test -x` catches an archive that unpacked into a shape that puts no runnable probcli where the rest of the plugin looks for it.

**`coverage: failed — probcli printed no coverage census`**: you are running ProB 1.16.0 or newer, whose coverage census z-spec cannot read. Confirm with `~/Applications/ProB/probcli -version`, then reinstall 1.15.1 using the block for your platform above. The model check itself is unaffected — only the coverage tier fails — and the reason is under "Choosing a version" above. Tracked as bead `z-spec-v0m`.

**"extracted ... but there is no executable probcli at ~/Applications/ProB/probcli"**: the archive downloaded and unpacked, but upstream repackaged it into a shape the install block does not recognise. List what you actually got and find the binary:

```bash
unzip -Z1 ~/Applications/ProB.macos.zip | head -20        # macOS
tar -tzf ~/Applications/ProB.linux64.tar.gz | head -20    # Linux
```

The install block handles a flat archive and one wrapped in a single top-level `ProB/`. For anything else — a deeper or differently-named wrapper — point `$PROBCLI` at wherever the binary actually landed:

```bash
export PROBCLI="$HOME/Applications/ProB/ProB/probcli"   # wherever it really is
```

That is the supported override, not a workaround, and it is honoured on both routes to probcli. Commands that go through the engine — `/z-spec:test`, `/z-spec:doctor` — reach it via `resolve_probcli()`, which checks `$PROBCLI` before `PATH` and before the conventional path. The `b-*` commands, which shell out to probcli directly, resolve it as `PROBCLI="${PROBCLI:-$HOME/Applications/ProB/probcli}"`. Either way the environment variable wins. `~/Applications/ProB/probcli` is only the default for when nothing says otherwise. Moving the extracted tree by hand also works, but it is the more laborious of the two and nothing requires it.

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

Upstream documents this as `curl ... | sh`, but a transfer that drops partway
through has already fed the shell a truncated script by the time curl reports
the failure, leaving a half-installed toolchain behind. Land the script first,
then run it, so a failed download installs nothing at all.

`-y` accepts the defaults. The installer checks whether its stdout is a
terminal and refuses to continue without it — "Unable to run interactively. Run
with -y to accept defaults." — so an agent, whose stdout is captured, needs the
flag every time. A human running this in their own terminal can drop `-y` to
get the interactive prompt.

```bash
# Same preflight as the probcli blocks: a missing curl exits 127 and would
# otherwise be reported below as a failed download.
command -v curl >/dev/null || {
  echo "ERROR: curl is not installed, and this block needs it" >&2
  exit 1
}

curl -fsSL -o ~/elan-init.sh https://elan.lean-lang.org/elan-init.sh || {
  echo "ERROR: could not download the elan installer" >&2
  exit 1
}

chmod +x ~/elan-init.sh || {
  echo "ERROR: could not make the elan installer executable" >&2
  exit 1
}

# Run the script directly rather than through `sh`. This command needs no
# general shell interpreter to be reachable, only this one downloaded file,
# and alongside the curl grant a bare `sh` would compose into a
# fetch-then-execute-anything pair.
~/elan-init.sh -y || {
  echo "ERROR: the elan installer failed; lean and lake are not installed" >&2
  exit 1
}

# The installer's exit code is not proof it installed anything, for the same
# reason curl's was not. It installs three tools, so check all three: a partial
# install that produced elan alone would otherwise be reported as success, and
# /z-spec:prove needs lean and lake, not elan.
for lean_tool in elan lean lake; do
  # Resolve into a variable and invoke that, rather than invoking the path
  # directly: a command whose text is a fixed path with a variable embedded in
  # it cannot be named by an allowed-tools entry, because the entry would have
  # to match text the variable has not been substituted into yet.
  LEAN_BIN=~/.elan/bin/"$lean_tool"

  test -x "$LEAN_BIN" || {
    echo "ERROR: the elan installer reported success but there is no" >&2
    echo "       executable at $LEAN_BIN" >&2
    exit 1
  }

  LEAN_OUT="$("$LEAN_BIN" --version 2>&1)" || {
    echo "ERROR: $LEAN_BIN is installed but would not run:" >&2
    printf '%s\n' "$LEAN_OUT" >&2
    exit 1
  }

  printf '%s\n' "$LEAN_OUT"
done
```

The installer stays at `~/elan-init.sh`; nothing here deletes it. Remove it by
hand once Lean works — `rm ~/elan-init.sh` — or leave it, which costs a few
kilobytes and gives you something to re-run. Deleting it automatically would
mean this command holds a grant to run `rm`, and a one-line convenience is not
worth that.

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

**"could not download the elan installer"**: the fetch failed before anything was installed, so nothing is half-done. Check the URL is reachable — `curl -fsSLI https://elan.lean-lang.org/elan-init.sh` — and retry. If your network needs a proxy, curl reads `https_proxy` from the environment.

**"the elan installer failed; lean and lake are not installed"** or **"the elan installer reported success but there is no executable at ~/.elan/bin/elan"**: read the installer's own output above the error — it names the cause. The usual ones are an unsupported platform, no write permission on `$HOME/.elan`, or a stale `~/.elan` from a previous partial install. The downloaded script stays at `~/elan-init.sh` whether the install succeeded or failed, so you can inspect it or re-run it by hand with `~/elan-init.sh -y`; it is safe to delete once Lean works. Lean is optional: `/z-spec:check` and `/z-spec:test` do not need it, only `/z-spec:prove` does.

**"elan: command not found" after install**: Run `source "$HOME/.elan/env"` or restart your terminal.

**Slow first build**: The first `lake build` in a Mathlib project downloads precompiled dependencies (~2 GB). Run `lake exe cache get` first to fetch the cache.

**"no toolchain installed"**: Run `elan default leanprover/lean4:stable` to set the default toolchain.

### 6. Verify Installation

Everything is installed; now confirm each tool answers.

Resolve each tool the way the engine does, rather than by bare name. The
`export PATH` lines in the steps above are instructions to paste into a shell
profile — they are not in effect in the session that just ran the install, so a
bare `fuzz` or `probcli` on the very next line after a clean install reports
`command not found` and makes a working installation look like a failed one.
`$FUZZ` and `$PROBCLI` take precedence, as they do in the engine, so a spec
verified here is verified against the binary the tools will use. Each block
resolves them again, because each is a separate shell invocation.

The two resolvers differ, and the difference matters. `resolve_probcli()` falls
back to `~/Applications/ProB/probcli` when nothing else names one;
`resolve_fuzz()` has no such fallback — it is `$FUZZ`, then `PATH`, and nothing
else. A fuzz binary reachable only by its full path is one `/z-spec:check` will
not find, so this block declines to find it either.

```bash
if [ -n "${FUZZ:-}" ] && [ -f "$FUZZ" ]; then
  FUZZ_BIN="$FUZZ"
else
  FUZZ_BIN="$(command -v fuzz 2>/dev/null)"
fi

test -x "$FUZZ_BIN" || {
  echo "ERROR: no runnable fuzz. Resolved to '${FUZZ_BIN:-nothing}' — it is" >&2
  echo "       not on PATH, or \$FUZZ names something that is missing or not" >&2
  echo "       executable. See step 3." >&2
  exit 1
}

if [ -n "${PROBCLI:-}" ] && [ -f "$PROBCLI" ]; then
  PROBCLI_BIN="$PROBCLI"
else
  PROBCLI_BIN="$(command -v probcli 2>/dev/null || echo "$HOME/Applications/ProB/probcli")"
fi

test -x "$PROBCLI_BIN" || {
  echo "ERROR: no runnable probcli at '$PROBCLI_BIN' — see step 4." >&2
  exit 1
}

# Test fuzz
mkdir -p .tmp
echo '\begin{zed}[X]\end{zed}' > .tmp/test.tex
"$FUZZ_BIN" -t .tmp/test.tex

# Test probcli with Z. Assert the version, as step 4 does: printing the banner
# and moving on would pass a 1.16.x, which runs everything here and then fails
# the coverage tier of every specification.
PROB_OUT="$("$PROBCLI_BIN" -version 2>&1)" || {
  echo "ERROR: $PROBCLI_BIN would not run:" >&2
  printf '%s\n' "$PROB_OUT" >&2
  exit 1
}

PROB_VER="$(printf '%s\n' "$PROB_OUT" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"

test "$PROB_VER" = "1.15.1" || {
  echo "ERROR: expected ProB 1.15.1, but $PROBCLI_BIN reports:" >&2
  printf '%s\n' "$PROB_OUT" >&2
  echo "       See 'Choosing a version' in step 4." >&2
  exit 1
}

printf '%s\n' "$PROB_OUT"

# Test the Lean toolchain. It is optional — only /z-spec:prove needs it — so
# absence is not a failure, but say which state each tool is in rather than
# leaving it to a command-not-found. Ask about the three separately: a partial
# install, or a Lean put there by some other route, can leave lean on PATH
# without elan or lake, and prove checks lean and lake independently too.
# /z-spec:prove looks on PATH and nowhere else — no $LEAN override, no ~/.elan
# fallback — so a binary reachable only at ~/.elan/bin is one prove will not
# find.
for lean_tool in elan lean lake; do
  if command -v "$lean_tool" >/dev/null 2>&1; then
    "$lean_tool" --version
  elif [ -x ~/.elan/bin/"$lean_tool" ]; then
    echo "$lean_tool: at ~/.elan/bin but NOT on PATH — /z-spec:prove will not" >&2
    echo "      see it until you run source \"\$HOME/.elan/env\"." >&2
  else
    echo "$lean_tool: not installed (optional)"
  fi
done
```

Create a simple test spec and run both tools:

```bash
if [ -n "${FUZZ:-}" ] && [ -f "$FUZZ" ]; then
  FUZZ_BIN="$FUZZ"
else
  FUZZ_BIN="$(command -v fuzz 2>/dev/null)"
fi

test -x "$FUZZ_BIN" || {
  echo "ERROR: no runnable fuzz. Resolved to '${FUZZ_BIN:-nothing}' — it is" >&2
  echo "       not on PATH, or \$FUZZ names something that is missing or not" >&2
  echo "       executable. See step 3." >&2
  exit 1
}

if [ -n "${PROBCLI:-}" ] && [ -f "$PROBCLI" ]; then
  PROBCLI_BIN="$PROBCLI"
else
  PROBCLI_BIN="$(command -v probcli 2>/dev/null || echo "$HOME/Applications/ProB/probcli")"
fi

test -x "$PROBCLI_BIN" || {
  echo "ERROR: no runnable probcli at '$PROBCLI_BIN' — see step 4." >&2
  exit 1
}

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

"$FUZZ_BIN" -t .tmp/test_spec.tex && echo "fuzz: OK"
"$PROBCLI_BIN" .tmp/test_spec.tex -init && echo "probcli: OK"
```

Test probcli with a B machine:

```bash
if [ -n "${PROBCLI:-}" ] && [ -f "$PROBCLI" ]; then
  PROBCLI_BIN="$PROBCLI"
else
  PROBCLI_BIN="$(command -v probcli 2>/dev/null || echo "$HOME/Applications/ProB/probcli")"
fi

test -x "$PROBCLI_BIN" || {
  echo "ERROR: no runnable probcli at '$PROBCLI_BIN' — see step 4." >&2
  exit 1
}

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

"$PROBCLI_BIN" .tmp/test_machine.mch -init && echo "probcli B: OK"
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
| probcli | ✓ Installed 1.15.1 | ~/Applications/ProB/probcli |
| elan | ✓ Installed | ~/.elan/bin/elan |
| lean | ✓ Installed | ~/.elan/bin/lean |
| lake | ✓ Installed | ~/.elan/bin/lake |

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

