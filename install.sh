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

VERSION="0.16.0"
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

if [ "$SKIP_PLUGIN" = "0" ]; then
  # --- Step 5: Register marketplace ---

  info "Registering Punt Labs marketplace..."

  if claude plugin marketplace list < /dev/null 2>/dev/null | grep -q "$MARKETPLACE_NAME"; then
    ok "marketplace already registered"
    claude plugin marketplace update "$MARKETPLACE_NAME" < /dev/null 2>/dev/null || true
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
      git config --global --unset url."https://github.com/".insteadOf 2>/dev/null || true
      NEED_HTTPS_REWRITE=0
    fi
  }
  trap cleanup_https_rewrite EXIT INT TERM

  if ! ssh -n -o StrictHostKeyChecking=accept-new -o BatchMode=yes -o ConnectTimeout=5 -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    warn "SSH auth to GitHub unavailable, using HTTPS fallback"
    git config --global url."https://github.com/".insteadOf "git@github.com:"
    NEED_HTTPS_REWRITE=1
  fi

  # --- Step 7: Install plugin ---

  info "Installing $PLUGIN_NAME plugin..."

  claude plugin uninstall "${PLUGIN_NAME}@${MARKETPLACE_NAME}" < /dev/null 2>/dev/null || true
  if ! claude plugin install "${PLUGIN_NAME}@${MARKETPLACE_NAME}" < /dev/null; then
    cleanup_https_rewrite
    fail "Failed to install $PLUGIN_NAME"
  fi
  if ! claude plugin list < /dev/null 2>/dev/null | grep -q "$PLUGIN_NAME@$MARKETPLACE_NAME"; then
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

# The final message is gated on the SKIP_PLUGIN boolean, not on the reason for
# skipping: the capability-absent auto-skip and the explicit --no-plugin skip
# print the SAME CLI-only block. This prevents the common bug of emitting a
# "restart to activate the plugin" line when no plugin was ever installed.
if [ "$SKIP_PLUGIN" = "1" ]; then
  printf '%b%b%s CLI installed (CLI-only mode — Claude Code plugin skipped)%b\n\n' "$GREEN" "$BOLD" "$BINARY" "$NC"
  printf 'The CLI is fully functional via the command line and MCP ("%s mcp").\n' "$BINARY"
  printf 'To get started:\n\n'
  printf '  %s doctor                 # check fuzz/probcli availability\n' "$BINARY"
  printf '  %s check <spec.tex>       # type-check a Z spec with fuzz\n' "$BINARY"
  printf '  %s test <spec.tex>        # animate and model-check with probcli\n\n' "$BINARY"
  printf '%s\n' 'To add the Claude Code plugin later, re-run the installer without' \
    '--no-plugin (and with ZSPEC_NO_PLUGIN unset). The plugin requires the' \
    'claude CLI and git to be installed.'
  printf '\n'
else
  printf '%b%b%s is ready!%b\n\n' "$GREEN" "$BOLD" "$PLUGIN_NAME" "$NC"
  printf 'Restart Claude Code, then type /z-spec:help to get started.\n'
  printf 'Run /z-spec:setup all to install fuzz and probcli.\n\n'
fi
