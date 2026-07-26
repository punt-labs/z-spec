#!/usr/bin/env bash
set -euo pipefail

# Restore dev plugin state on main after a release tag.
#
# Usage:
#   scripts/restore-dev-plugin.sh [release-prep-commit]
#
# With no argument, auto-detects the last "prepare plugin for release" commit and
# restores from its parent. Checking out the parent's plugin.json and commands/
# restores all three release-time swaps at once: the -dev name, the uv-run MCP
# command, and the -dev command twins.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_JSON="${REPO_ROOT}/.claude-plugin/plugin.json"

# Preflight: abort if the repo has uncommitted changes.
if [[ -n "$(git -C "$REPO_ROOT" status --porcelain -uno)" ]]; then
  echo "restore-dev-plugin: repository has uncommitted changes; commit or stash first" >&2
  exit 1
fi

RELEASE_PREP_COMMIT="${1:-}"
if [[ -z "$RELEASE_PREP_COMMIT" ]]; then
  RELEASE_PREP_COMMIT="$(git -C "$REPO_ROOT" log -n 1 --grep='prepare plugin for release' --pretty=format:%H || true)"
  if [[ -z "$RELEASE_PREP_COMMIT" ]]; then
    echo "restore-dev-plugin: no 'prepare plugin for release' commit found; pass a commit or tag" >&2
    exit 1
  fi
fi

echo "Restoring dev state from parent of ${RELEASE_PREP_COMMIT:0:12}"
git -C "$REPO_ROOT" checkout "${RELEASE_PREP_COMMIT}^" -- "$PLUGIN_JSON"

# Restore the -dev command twins if the parent commit had them.
if git -C "$REPO_ROOT" ls-tree "${RELEASE_PREP_COMMIT}^" -- commands/ | grep -q -e '-dev\.md'; then
  git -C "$REPO_ROOT" checkout "${RELEASE_PREP_COMMIT}^" -- commands/
fi

git -C "$REPO_ROOT" add "$PLUGIN_JSON" commands/
git -C "$REPO_ROOT" commit --no-verify -m "chore: restore dev plugin state"
