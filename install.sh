#!/bin/sh
# Install z-spec — formal Z specifications for Claude Code.
# Usage: curl -fsSL https://raw.githubusercontent.com/punt-labs/z-spec/<SHA>/install.sh | sh
set -eu

# --- Colors (disabled when not a terminal) ---
if [ -t 1 ]; then
  BOLD='\033[1m' GREEN='\033[32m' YELLOW='\033[33m' NC='\033[0m'
else
  BOLD='' GREEN='' YELLOW='' NC=''
fi

info() { printf '%b▶%b %s\n' "$BOLD" "$NC" "$1"; }
ok()   { printf '  %b✓%b %s\n' "$GREEN" "$NC" "$1"; }
warn() { printf '  %b!%b %s\n' "$YELLOW" "$NC" "$1" >&2; }
fail() { printf '  %b✗%b %s\n' "$YELLOW" "$NC" "$1" >&2; exit 1; }

VERSION="0.20.0"
MARKETPLACE_REPO="punt-labs/claude-plugins"
MARKETPLACE_NAME="punt-labs"
PLUGIN_NAME="z-spec"
PACKAGE="punt-z-spec"
BINARY="z-spec"

usage() {
  printf '%s\n' \
    'install.sh — install the z-spec CLI and (by default) the Claude Code plugin' \
    '' \
    'Usage: curl -fsSL .../install.sh | sh                    # CLI + plugin' \
    '       curl -fsSL .../install.sh | sh -s -- --no-plugin  # CLI only' \
    '' \
    'Options:' \
    '  --no-plugin   Install the CLI only; skip the Claude Code plugin.' \
    '  -h, --help    Print this help and exit.' \
    '' \
    'Environment:' \
    '  ZSPEC_NO_PLUGIN=1   Same as --no-plugin, for argument-hostile contexts:' \
    '                      curl -fsSL .../install.sh | ZSPEC_NO_PLUGIN=1 sh'
}

# --- Argument parsing ---
# Runs before any work. Over a pipe (curl … | sh -s -- --no-plugin) a misspelled
# flag must not silently install the plugin the user asked to skip, so unknown
# options are a usage error (exit 2).
NO_PLUGIN_REQUESTED=0
for arg in "$@"; do
  case "$arg" in
    --no-plugin) NO_PLUGIN_REQUESTED=1 ;;
    -h|--help)   usage; exit 0 ;;
    *)           printf 'install.sh: unknown option: %s\n' "$arg" >&2; usage >&2; exit 2 ;;
  esac
done

# --- Step 1: Prerequisites ---

info "Checking prerequisites..."

# curl is a hard prerequisite: it fetches the uv installer and is the transport
# for the CLI install itself. Absence aborts — the CLI cannot be installed.
if command -v curl >/dev/null 2>&1; then
  ok "curl found"
else
  fail "'curl' not found. Install curl first."
fi

# Resolve whether to skip the plugin. A single boolean OR-combines the explicit
# request (--no-plugin / ZSPEC_NO_PLUGIN=1) with capability auto-skip: the
# plugin needs the claude CLI to install and git to clone, so absence of either
# skips the plugin step (never aborts) while the CLI install proceeds. There is
# deliberately no counter-flag to force the plugin on — you cannot install it
# without claude, and explicit-request and capability-absence never conflict.
SKIP_PLUGIN=0
if [ "$NO_PLUGIN_REQUESTED" = "1" ] || [ "${ZSPEC_NO_PLUGIN:-}" = "1" ]; then
  ok "plugin install skipped by request (--no-plugin / ZSPEC_NO_PLUGIN=1)"
  SKIP_PLUGIN=1
fi

if command -v claude >/dev/null 2>&1; then
  ok "claude CLI found"
else
  warn "claude CLI not found — skipping plugin install (CLI-only)"
  warn "Install from: https://docs.anthropic.com/en/docs/claude-code"
  SKIP_PLUGIN=1
fi

if command -v git >/dev/null 2>&1; then
  ok "git found"
else
  warn "git not found — skipping plugin install (required to clone the plugin)"
  SKIP_PLUGIN=1
fi

# --- Step 2: uv ---

info "Checking uv..."

if command -v uv >/dev/null 2>&1; then
  ok "uv already installed"
else
  info "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  if [ -f "$HOME/.local/bin/env" ]; then
    # shellcheck source=/dev/null
    . "$HOME/.local/bin/env"
  elif [ -f "$HOME/.cargo/env" ]; then
    # shellcheck source=/dev/null
    . "$HOME/.cargo/env"
  fi
  export PATH="$HOME/.local/bin:$PATH"
  if ! command -v uv >/dev/null 2>&1; then
    fail "uv install succeeded but 'uv' not found on PATH. Restart your shell and re-run."
  fi
  ok "uv installed"
fi

# --- Step 3: Python 3.13+ ---

info "Checking Python..."

PYTHON_FLAG=""
HAVE_PYTHON=0
if command -v python3 >/dev/null 2>&1; then
  PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
  PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
  if [ "$PY_MAJOR" -gt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 13 ]; }; then
    ok "Python ${PY_MAJOR}.${PY_MINOR}"
    HAVE_PYTHON=1
  fi
fi

if [ "$HAVE_PYTHON" = "0" ]; then
  info "Installing Python 3.13 via uv..."
  uv python install 3.13 || fail "Failed to install Python 3.13"
  ok "Python 3.13 (uv-managed)"
  PYTHON_FLAG="--python 3.13"
fi

# --- Step 4: Install z-spec CLI ---

info "Installing $PACKAGE..."

# shellcheck disable=SC2086
uv tool install --force $PYTHON_FLAG "$PACKAGE==$VERSION" || fail "Failed to install $PACKAGE==$VERSION"
ok "$PACKAGE installed"

if ! command -v "$BINARY" >/dev/null 2>&1; then
  export PATH="$HOME/.local/bin:$PATH"
  if ! command -v "$BINARY" >/dev/null 2>&1; then
    fail "$PACKAGE installed but '$BINARY' not found on PATH"
  fi
fi

ok "$BINARY $(command -v "$BINARY")"

# --- Step 4.5: Install probcli ---
#
# Only /z-spec:check (fuzz type-checking) works without probcli. Every other
# command -- test, model2code, code2model, oracle, animation -- needs it. An
# install that finishes without probcli and then prints "ready!" is the exact
# bug z-spec-68e fixed in plugin/commands/setup.md, just one layer up: reports
# success while the tool cannot do most of what it is for. So probcli install
# is part of the default flow, not a follow-up step.
#
# fuzz is deliberately NOT auto-installed here: it must be compiled from
# source (git clone + make + sudo make install into a TeX distribution most
# machines do not have), which is a fundamentally riskier and slower operation
# to run unattended inside a piped curl | sh than downloading a static binary.
# HAVE_FUZZ below only detects it for the final summary, never installs it.

info "Installing probcli..."

PROB_VERSION=1.15.1
PROB_BASE="https://stups.hhu-hosting.de/downloads/prob/tcltk/releases"
PROB_HOME="$HOME/Applications/ProB"

# Mirror src/punt_zspec/prob.py's resolve_probcli() exactly: $PROBCLI (if it
# names a file) wins, then PATH, then the conventional path -- in that order.
# Checking only the conventional path here would let install.sh report a
# state that disagrees with what the engine and every other z-spec command
# actually resolve to, which is exactly the class of bug this whole change
# exists to close.
resolve_probcli_path() {
  if [ -n "${PROBCLI:-}" ] && [ -f "$PROBCLI" ]; then
    printf '%s\n' "$PROBCLI"
    return 0
  fi
  found="$(command -v probcli 2>/dev/null)" || found=""
  if [ -n "$found" ]; then
    printf '%s\n' "$found"
    return 0
  fi
  if [ -f "$PROB_HOME/probcli" ]; then
    printf '%s\n' "$PROB_HOME/probcli"
    return 0
  fi
  return 1
}

# Mirror src/punt_zspec/fuzz.py's resolve_fuzz(): $FUZZ (if a file), then
# PATH. No conventional-path fallback -- fuzz has none, unlike probcli.
resolve_fuzz_path() {
  if [ -n "${FUZZ:-}" ] && [ -f "$FUZZ" ]; then
    printf '%s\n' "$FUZZ"
    return 0
  fi
  found="$(command -v fuzz 2>/dev/null)" || found=""
  if [ -n "$found" ]; then
    printf '%s\n' "$found"
    return 0
  fi
  return 1
}

install_probcli() (
  # Subshell: a failure anywhere here returns nonzero without aborting the
  # rest of install.sh under set -e, and every path below is explicit so a
  # partial failure never gets reported as success.
  set -eu

  case "$(uname -s)" in
    Darwin) PROB_ARCHIVE_NAME="ProB.macos.zip" ;;
    Linux)  PROB_ARCHIVE_NAME="ProB.linux64.tar.gz" ;;
    *)      echo "  ! unsupported OS for probcli: $(uname -s) -- skipping" >&2; return 1 ;;
  esac

  for tool in curl file; do
    command -v "$tool" >/dev/null 2>&1 || {
      echo "  ! $tool not found -- cannot install probcli" >&2
      return 1
    }
  done
  case "$PROB_ARCHIVE_NAME" in
    *.zip) command -v unzip >/dev/null 2>&1 || { echo "  ! unzip not found -- cannot install probcli" >&2; return 1; } ;;
    *.tar.gz) command -v tar >/dev/null 2>&1 || { echo "  ! tar not found -- cannot install probcli" >&2; return 1; } ;;
  esac

  # Already at the right version, wherever the engine would actually find it
  # ($PROBCLI, PATH, or the conventional path)? Skip the download entirely --
  # and do not install into $PROB_HOME on top of it, which would leave two
  # copies and nothing pointing at which one is authoritative.
  EXISTING="$(resolve_probcli_path)" && [ -x "$EXISTING" ] || EXISTING=""
  if [ -n "$EXISTING" ]; then
    EXISTING_OUT="$("$EXISTING" -version 2>&1)" || EXISTING_OUT=""
    EXISTING_VER="$(printf '%s\n' "$EXISTING_OUT" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
    if [ "$EXISTING_VER" = "$PROB_VERSION" ]; then
      echo "  ✓ probcli $EXISTING (already $PROB_VERSION)"
      return 0
    fi
  fi

  mkdir -p "$PROB_HOME" || { echo "  ! could not create $PROB_HOME" >&2; return 1; }

  PROB_URL="$PROB_BASE/$PROB_VERSION/$PROB_ARCHIVE_NAME"
  ARCHIVE="$HOME/Applications/$PROB_ARCHIVE_NAME"

  # -f makes curl exit nonzero on 404/5xx instead of saving the error page as
  # if it were the archive -- the exact silent failure z-spec-68e fixed.
  curl -fL -o "$ARCHIVE" "$PROB_URL" || {
    echo "  ! download failed: $PROB_URL" >&2
    return 1
  }

  case "$PROB_ARCHIVE_NAME" in
    *.zip)
      unzip -tq "$ARCHIVE" || {
        echo "  ! $PROB_URL did not return a zip archive (got: $(file -b "$ARCHIVE"))" >&2
        return 1
      }
      LISTING="$(unzip -Z1 "$ARCHIVE")" || { echo "  ! could not list $ARCHIVE" >&2; return 1; }
      if printf '%s\n' "$LISTING" | grep -q '^ProB/'; then DEST="$HOME/Applications"; else DEST="$PROB_HOME"; fi
      unzip -oq "$ARCHIVE" -d "$DEST" || { echo "  ! could not extract $ARCHIVE into $DEST" >&2; return 1; }
      ;;
    *.tar.gz)
      LISTING="$(tar -tzf "$ARCHIVE")" || {
        echo "  ! $PROB_URL did not return a gzip tarball (got: $(file -b "$ARCHIVE"))" >&2
        return 1
      }
      if printf '%s\n' "$LISTING" | grep -q '^ProB/'; then DEST="$HOME/Applications"; else DEST="$PROB_HOME"; fi
      tar -xzf "$ARCHIVE" -C "$DEST" || { echo "  ! could not extract $ARCHIVE into $DEST" >&2; return 1; }
      ;;
  esac

  # Do not trust the archive's exec bit -- but do not conflate "chmod was
  # refused" with "nothing is there": whether the file exists first is what
  # separates the two causes, and reporting either as the other sends the
  # reader after the wrong problem, same as plugin/commands/setup.md.
  CHMOD_ERR="$(chmod +x "$PROB_HOME/probcli" 2>&1)" || true

  test -x "$PROB_HOME/probcli" || {
    if [ -e "$PROB_HOME/probcli" ]; then
      echo "  ! probcli is at $PROB_HOME/probcli but could not be made" >&2
      echo "    executable: ${CHMOD_ERR:-chmod reported no reason}" >&2
    else
      echo "  ! extracted $ARCHIVE but there is no probcli at" >&2
      echo "    $PROB_HOME/probcli. The archive layout is not what this" >&2
      echo "    script expects." >&2
    fi
    return 1
  }

  PROB_OUT="$("$PROB_HOME/probcli" -version 2>&1)" || {
    echo "  ! $PROB_HOME/probcli is installed but would not run:" >&2
    printf '%s\n' "$PROB_OUT" >&2
    return 1
  }

  # Exact match, not substring: a future 1.15.10 must not silently pass as
  # 1.15.1.
  PROB_VER="$(printf '%s\n' "$PROB_OUT" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
  test "$PROB_VER" = "$PROB_VERSION" || {
    echo "  ! expected probcli $PROB_VERSION, got: $PROB_VER" >&2
    return 1
  }

  echo "  ✓ probcli $PROB_HOME/probcli ($PROB_VERSION)"
)

install_probcli || warn "probcli install failed -- see the error above"

# The pointer to /z-spec:setup only makes sense when the plugin is
# installed; a CLI-only install has no slash commands to run.
if [ "$SKIP_PLUGIN" = "0" ]; then
  PROBCLI_SETUP_HINT="or install by hand: /z-spec:setup probcli"
  FUZZ_SETUP_HINT="see /z-spec:setup fuzz"
else
  PROBCLI_SETUP_HINT="see 'Choosing a version' in plugin/commands/setup.md for the manual steps"
  FUZZ_SETUP_HINT="see plugin/commands/setup.md for the manual build steps (no plugin installed to run /z-spec:setup)"
fi

# HAVE_PROBCLI is not install_probcli's return code: that function only ever
# manages $PROB_HOME. What matters is what the engine will actually resolve
# to (resolve_probcli_path, same precedence as resolve_probcli() in
# src/punt_zspec/prob.py) and whether that binary is genuinely 1.15.1 -- a
# stale or wrong-version probcli earlier on PATH would otherwise pass this
# check while every command that shells out to probcli finds the wrong one.
#
# PROBCLI_STATUS distinguishes the three outcomes the final summary needs to
# tell apart: nothing resolves at all ("absent"), something resolves but
# will not execute ("not-executable" -- a permissions/quarantine problem,
# not a missing install), or something resolves, runs, and is the wrong
# version ("wrong-version" -- a stale install shadowing the pinned one, not
# an absent one). Collapsing any two of these into "not found" sends the
# reader after the wrong fix.
HAVE_PROBCLI=0
PROBCLI_STATUS="absent"
RESOLVED_PROBCLI="$(resolve_probcli_path)" || RESOLVED_PROBCLI=""
if [ -z "$RESOLVED_PROBCLI" ]; then
  warn "probcli not found -- most z-spec commands need it. Re-run this"
  warn "installer, $PROBCLI_SETUP_HINT"
elif [ ! -x "$RESOLVED_PROBCLI" ]; then
  PROBCLI_STATUS="not-executable"
  warn "probcli resolves to $RESOLVED_PROBCLI, but it is not executable"
  warn "(permissions, or macOS quarantine) -- $PROBCLI_SETUP_HINT"
else
  RESOLVED_PROBCLI_OUT="$("$RESOLVED_PROBCLI" -version 2>&1)" || RESOLVED_PROBCLI_OUT=""
  RESOLVED_PROBCLI_VER="$(printf '%s\n' "$RESOLVED_PROBCLI_OUT" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
  if [ "$RESOLVED_PROBCLI_VER" = "$PROB_VERSION" ]; then
    HAVE_PROBCLI=1
    PROBCLI_STATUS="ok"
    ok "probcli $RESOLVED_PROBCLI ($PROB_VERSION)"
  else
    PROBCLI_STATUS="wrong-version"
    warn "probcli resolves to $RESOLVED_PROBCLI, version ${RESOLVED_PROBCLI_VER:-unreadable}"
    warn "-- not $PROB_VERSION. That is what every z-spec command will use."
  fi
fi

# Same resolution order as resolve_fuzz(): $FUZZ then PATH, no conventional
# fallback. fuzz has no pinned version to check against, so its only two
# states are "resolves and runs" and everything else.
HAVE_FUZZ=0
FUZZ_STATUS="absent"
RESOLVED_FUZZ="$(resolve_fuzz_path)" || RESOLVED_FUZZ=""
if [ -z "$RESOLVED_FUZZ" ]; then
  warn "fuzz not found -- type-checking (/z-spec:check) needs it"
  warn "fuzz must be built from source; $FUZZ_SETUP_HINT"
elif [ ! -x "$RESOLVED_FUZZ" ]; then
  FUZZ_STATUS="not-executable"
  warn "fuzz resolves to $RESOLVED_FUZZ, but it is not executable"
  warn "(permissions, or macOS quarantine) -- $FUZZ_SETUP_HINT"
else
  HAVE_FUZZ=1
  FUZZ_STATUS="ok"
  ok "fuzz $RESOLVED_FUZZ"
fi

if [ "$SKIP_PLUGIN" = "0" ]; then
  # --- Step 5: Register marketplace ---

  info "Registering Punt Labs marketplace..."

  if claude plugin marketplace list < /dev/null | grep -q "$MARKETPLACE_NAME"; then
    ok "marketplace already registered"
    claude plugin marketplace update "$MARKETPLACE_NAME" < /dev/null || warn "marketplace refresh failed; continuing with cached version"
  else
    claude plugin marketplace add "$MARKETPLACE_REPO" < /dev/null || fail "Failed to register marketplace"
    ok "marketplace registered"
  fi

  # --- Step 6: SSH fallback for plugin install ---

  # claude plugin install clones via SSH (git@github.com:...).
  # Users without SSH keys need an HTTPS fallback.
  NEED_HTTPS_REWRITE=0
  cleanup_https_rewrite() {
    if [ "$NEED_HTTPS_REWRITE" = "1" ]; then
      git config --global --unset url."https://github.com/".insteadOf '^git@github\.com:$' 2>/dev/null || warn "could not remove temporary git HTTPS rewrite; undo manually with: git config --global --unset url.\"https://github.com/\".insteadOf"
      NEED_HTTPS_REWRITE=0
    fi
  }
  trap cleanup_https_rewrite EXIT INT TERM

  if ! ssh -n -o StrictHostKeyChecking=accept-new -o BatchMode=yes -o ConnectTimeout=5 -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    warn "SSH auth to GitHub unavailable, using HTTPS fallback"
    git config --global --add url."https://github.com/".insteadOf "git@github.com:"
    NEED_HTTPS_REWRITE=1
  fi

  # --- Step 7: Install plugin ---

  info "Installing $PLUGIN_NAME plugin..."

  claude plugin uninstall "${PLUGIN_NAME}@${MARKETPLACE_NAME}" < /dev/null 2>/dev/null || true
  if ! claude plugin install "${PLUGIN_NAME}@${MARKETPLACE_NAME}" < /dev/null; then
    cleanup_https_rewrite
    fail "Failed to install $PLUGIN_NAME"
  fi
  if ! claude plugin list < /dev/null | grep -q "$PLUGIN_NAME@$MARKETPLACE_NAME"; then
    cleanup_https_rewrite
    fail "$PLUGIN_NAME install reported success but plugin not found"
  fi
  ok "$PLUGIN_NAME plugin installed"

  cleanup_https_rewrite
else
  info "Skipping plugin install (CLI-only mode)"
fi

# --- Step 8: Verify ---

info "Verifying installation..."
printf '\n'
"$BINARY" doctor || true
printf '\n'

# --- Done ---

# "Ready" means the toolchain actually works, not just that the CLI/plugin
# steps completed -- claiming otherwise is the exact bug this step exists to
# stop. HAVE_PROBCLI/HAVE_FUZZ reflect what was actually verified above, not
# what the installer attempted.
if [ "$HAVE_PROBCLI" = "1" ] && [ "$HAVE_FUZZ" = "1" ]; then
  READY=1
else
  READY=0
fi

if [ "$SKIP_PLUGIN" = "1" ]; then
  if [ "$READY" = "1" ]; then
    printf '%b%b%s CLI installed and ready (CLI-only mode — Claude Code plugin skipped)%b\n\n' "$GREEN" "$BOLD" "$BINARY" "$NC"
  else
    printf '%b%b%s CLI installed, but not fully ready (CLI-only mode — Claude Code plugin skipped)%b\n\n' "$YELLOW" "$BOLD" "$BINARY" "$NC"
  fi
  printf 'The z-spec CLI and its MCP server ("%s mcp") are installed.\n' "$BINARY"
  if [ "$READY" != "1" ]; then
    printf 'Run "%s doctor" to see what is still missing.\n' "$BINARY"
  fi
  printf 'To get started:\n\n'
  printf '  %s doctor                 # check fuzz/probcli availability\n' "$BINARY"
  printf '  %s check <spec.tex>       # type-check a Z spec with fuzz\n' "$BINARY"
  printf '  %s test <spec.tex>        # animate and model-check with probcli\n\n' "$BINARY"
  printf '%s\n' 'To add the Claude Code plugin later, re-run the installer without' \
    '--no-plugin (and with ZSPEC_NO_PLUGIN unset). The plugin requires the' \
    'claude CLI and git to be installed.'
  printf '\n'
elif [ "$READY" = "1" ]; then
  printf '%b%b%s is ready!%b\n\n' "$GREEN" "$BOLD" "$PLUGIN_NAME" "$NC"
  printf 'Restart Claude Code, then type /z-spec:help to get started.\n\n'
else
  printf '%b%b%s plugin installed, but the toolchain is incomplete%b\n\n' "$YELLOW" "$BOLD" "$PLUGIN_NAME" "$NC"
  printf 'Restart Claude Code, then run "%s doctor" (or /z-spec:doctor) to see what\n' "$BINARY"
  printf 'is still missing, and /z-spec:setup to install it.\n\n'
  # Only claim a command outright "works" or "does not work" when the status
  # is unambiguous (ok, or genuinely absent). "wrong-version" and
  # "not-executable" both mean a probcli/fuzz DOES resolve and (for
  # wrong-version) DOES run -- just not correctly -- which is a different
  # claim than "not available", and conflating them was the exact finding
  # this rewrite closes. The specific reason is already in the warning
  # printed above; this summary states only what is unambiguous.
  if [ "$PROBCLI_STATUS" = "absent" ] && [ "$FUZZ_STATUS" = "absent" ]; then
    printf 'Neither probcli nor fuzz is available: no z-spec command that touches a\n'
    printf 'spec will work yet.\n\n'
  elif [ "$PROBCLI_STATUS" = "absent" ] && [ "$FUZZ_STATUS" = "ok" ]; then
    printf 'fuzz is available, probcli is not: /z-spec:check (type-checking) works,\n'
    printf 'but /z-spec:test, model2code, code2model, oracle, and animation do not.\n\n'
  elif [ "$PROBCLI_STATUS" = "ok" ] && [ "$FUZZ_STATUS" = "absent" ]; then
    printf 'probcli is available, fuzz is not: model-checking and animation work,\n'
    printf 'but /z-spec:check (type-checking) does not.\n\n'
  else
    printf 'probcli or fuzz resolves to something that will not run correctly (see\n'
    printf 'the warning above naming which one and why) rather than being absent --\n'
    printf 'fixing that, not reinstalling from scratch, is what unblocks it.\n\n'
  fi
fi
