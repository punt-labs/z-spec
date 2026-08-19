#!/usr/bin/env bash
set -euo pipefail

# Prepare the plugin for release: swap the dev name to prod, rewrite the MCP
# server command to the installed binary, and remove the -dev command twins.
# The tagged commit carries only prod artifacts; the marketplace cache clones
# from it. scripts/restore-dev-plugin.sh puts main back into dev state.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Pathspecs are repo-relative: git rejects absolute pathspecs on some versions.
# The shippable surface lives under plugin/ so the marketplace can install it
# with a git-subdir source; both paths are inside that directory.
PLUGIN_JSON="plugin/.claude-plugin/plugin.json"
COMMANDS_DIR="plugin/commands"

# Preflight: abort if the repo has uncommitted changes to tracked files.
if [[ -n "$(git status --porcelain -uno)" ]]; then
  echo "release-plugin: repository has uncommitted changes; commit or stash first" >&2
  exit 1
fi

# The check above (-uno) skips untracked files so local scratch does not block a
# release. But an untracked (non-ignored) file under the paths this script
# rewrites would break the `git rm` of the twins; reject those specifically.
untracked_in_scope="$(git ls-files --others --exclude-standard -- "$COMMANDS_DIR" "$PLUGIN_JSON")"
if [[ -n "$untracked_in_scope" ]]; then
  echo "release-plugin: untracked files under ${COMMANDS_DIR}/ or plugin/.claude-plugin/; commit or remove them first:" >&2
  echo "$untracked_in_scope" >&2
  exit 1
fi

current_name="$(python3 -c "import json; print(json.load(open('${PLUGIN_JSON}'))['name'])")"
prod_name="${current_name%-dev}"

if [[ "$current_name" == "$prod_name" ]]; then
  echo "release-plugin: plugin name is already '${prod_name}' (no -dev suffix)" >&2
  exit 1
fi

echo "Swapping plugin name: ${current_name} -> ${prod_name}"
echo "Rewriting MCP command: uv run (working tree) -> installed 'z-spec' binary"
python3 -c "
import json, pathlib
p = pathlib.Path('${PLUGIN_JSON}')
d = json.loads(p.read_text())
d['name'] = '${prod_name}'
srv = d['mcpServers']['zspec']
srv['command'] = 'z-spec'
srv['args'] = ['mcp']
p.write_text(json.dumps(d, indent=2) + '\n')
"

# Remove the -dev command twins.

# A process substitution's exit status is invisible to `set -e`: if
# COMMANDS_DIR is wrong, find fails, the loop reads nothing, and the empty
# `dev_files` below reads as "this tree has no twins to strip" — a prod release
# tagged with every *-dev.md still in it. Demonstrated with COMMANDS_DIR set to
# a nonexistent path: the script printed "No -dev commands found" and carried on
# to commit. The directory is a precondition, so assert it before the find.
if [[ ! -d "$COMMANDS_DIR" ]]; then
  echo "release-plugin: no ${COMMANDS_DIR}/ in $(pwd); cannot tell 'no twins' from 'wrong path'" >&2
  exit 1
fi

dev_files=()
while IFS= read -r -d '' f; do
  dev_files+=("$f")
done < <(find "$COMMANDS_DIR" -name '*-dev.md' -print0)

if [[ ${#dev_files[@]} -eq 0 ]]; then
  echo "No -dev commands found — name and MCP swap only"
else
  for f in "${dev_files[@]}"; do
    echo "Removing: $(basename "$f")"
  done
  git rm "${dev_files[@]}"
fi

git add "$PLUGIN_JSON"
git commit --no-verify -m "chore: prepare plugin for release"
