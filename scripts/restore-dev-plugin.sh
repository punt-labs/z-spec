#!/usr/bin/env bash
set -euo pipefail

# Restore dev plugin state on main after a release tag.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Restore plugin.json from the commit before release prep
git -C "$REPO_ROOT" checkout HEAD~1 -- .claude-plugin/plugin.json
git -C "$REPO_ROOT" add .claude-plugin/plugin.json

# Restore -dev commands only if they were removed in the release prep commit
if git -C "$REPO_ROOT" diff HEAD~1 --name-only -- commands/ | grep -q '-dev\.md$'; then
  git -C "$REPO_ROOT" checkout HEAD~1 -- commands/
  git -C "$REPO_ROOT" add commands/
fi

git -C "$REPO_ROOT" commit --no-verify -m "chore: restore dev plugin state"
