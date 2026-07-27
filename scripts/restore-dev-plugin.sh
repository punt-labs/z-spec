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
cd "$REPO_ROOT"

# Pathspecs are repo-relative: git rejects absolute pathspecs on some versions.
PLUGIN_JSON=".claude-plugin/plugin.json"

# Preflight: abort if the repo has uncommitted changes to tracked files.
if [[ -n "$(git status --porcelain -uno)" ]]; then
  echo "restore-dev-plugin: repository has uncommitted changes; commit or stash first" >&2
  exit 1
fi

# The check above (-uno) skips untracked files so local scratch does not block a
# restore. But `git add commands/` below would sweep an untracked (non-ignored)
# file under commands/ into the restore commit; reject those specifically.
untracked_in_scope="$(git ls-files --others --exclude-standard -- commands "$PLUGIN_JSON")"
if [[ -n "$untracked_in_scope" ]]; then
  echo "restore-dev-plugin: untracked files under commands/ or .claude-plugin/; commit or remove them first:" >&2
  echo "$untracked_in_scope" >&2
  exit 1
fi

# Guard: only restore when the working tree is in released (prod) state. Release
# prep swaps the name to 'z-spec'; restore swaps it back to 'z-spec-dev'. Running
# against a dev tree — a second run, or a run against an older release-prep — would
# check out the parent's commands/ over live command edits and lose them.
current_name="$(python3 -c "import json; print(json.load(open('${PLUGIN_JSON}'))['name'])")"
if [[ "$current_name" != "z-spec" ]]; then
  echo "restore-dev-plugin: plugin name is '${current_name}', not 'z-spec'; refusing to run (working tree is not in released prod state)" >&2
  exit 1
fi

RELEASE_PREP_COMMIT="${1:-}"
if [[ -z "$RELEASE_PREP_COMMIT" ]]; then
  RELEASE_PREP_COMMIT="$(git log -n 1 --grep='prepare plugin for release' --pretty=format:%H || true)"
  if [[ -z "$RELEASE_PREP_COMMIT" ]]; then
    echo "restore-dev-plugin: no 'prepare plugin for release' commit found; pass a commit or tag" >&2
    exit 1
  fi
fi

echo "Restoring dev state from parent of ${RELEASE_PREP_COMMIT:0:12}"
git checkout "${RELEASE_PREP_COMMIT}^" -- "$PLUGIN_JSON"

# Restore the -dev command twins if the parent commit had them.
if git ls-tree "${RELEASE_PREP_COMMIT}^" -- commands/ | grep -q -e '-dev\.md'; then
  git checkout "${RELEASE_PREP_COMMIT}^" -- commands/
fi

git add "$PLUGIN_JSON" commands/
git commit --no-verify -m "chore: restore dev plugin state"
