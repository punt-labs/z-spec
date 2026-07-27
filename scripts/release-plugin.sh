#!/usr/bin/env bash
set -euo pipefail

# Prepare the plugin for release: swap the dev name to prod, rewrite the MCP
# server command to the installed binary, and remove the -dev command twins.
# The tagged commit carries only prod artifacts; the marketplace cache clones
# from it. scripts/restore-dev-plugin.sh puts main back into dev state.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Pathspecs are repo-relative: git rejects absolute pathspecs on some versions.
PLUGIN_JSON=".claude-plugin/plugin.json"
COMMANDS_DIR="commands"

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
  echo "release-plugin: untracked files under ${COMMANDS_DIR}/ or .claude-plugin/; commit or remove them first:" >&2
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
