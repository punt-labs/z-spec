#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 || ! -d $1 || ! -x $2/probcli ]]; then
    printf 'usage: %s EXISTING_OUTPUT_DIRECTORY PROB_INSTALL_DIRECTORY\n' "$0" >&2
    exit 2
fi
if [[ $(uname -s)-$(uname -m) != Linux-x86_64 ]]; then
    printf 'The z-spec handoff runtime must be built on Linux x86-64.\n' >&2
    exit 1
fi

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
common=$(git -C "$repo" rev-parse --path-format=absolute --git-common-dir)
local_root=$(dirname -- "$common")/.punt-labs/local/ethos
output=$(cd -- "$1" && pwd -P)
prob=$(cd -- "$2" && pwd -P)
prob_version=$(sed -n 's/^PROB_VERSION=//p' "$repo/install.sh")
if [[ $("$prob/probcli" -version) != *"VERSION $prob_version-final"* ]]; then
    printf 'Expected the pinned ProB %s installation.\n' "$prob_version" >&2
    exit 1
fi

uv=$(command -v uv)
uvx=$(command -v uvx)
uv_version=$("$uv" --version | cut -d ' ' -f 2)
python=$(uv python find --managed-python --no-project 3.13)
python_home=$("$python" -I -c 'import sys; print(sys.base_prefix)')
node_home=$(dirname -- "$(dirname -- "$(node -p 'process.execPath')")")
if [[ ! -f $node_home/LICENSE || ! -f $node_home/lib/node_modules/npm/bin/npx-cli.js ]]; then
    printf 'Use an upstream Node distribution with npm, npx, and its license (e.g. via nvm).\n' >&2
    exit 1
fi
fuzz_repo=$(sed -n 's/^FUZZ_REPO="\(.*\)"$/\1/p' "$repo/install.sh")
fuzz_ref=$(sed -n 's/^FUZZ_REF="\(.*\)"$/\1/p' "$repo/install.sh")
if [[ -z $fuzz_repo || ! $fuzz_ref =~ ^[0-9a-f]{40}$ ]]; then
    printf 'Could not read the pinned fuzz source from install.sh.\n' >&2
    exit 1
fi

mkdir -p "$local_root"
work=$(mktemp -d "$local_root/runtime-build.XXXXXX")
staged=
trap 'rm -rf -- "$work"; if [[ -n $staged ]]; then rm -f -- "$staged"; fi' EXIT
runtime=$work/runtime
mkdir -p "$runtime/bin" "$runtime/node/bin" "$runtime/node/lib/node_modules" \
    "$runtime/licenses" "$work/home" "$work/tmp"
fuzz_source=$work/fuzz
(
    git clone --quiet --no-checkout "$fuzz_repo" "$fuzz_source"
    cd "$fuzz_source"
    git checkout --quiet --detach "$fuzz_ref"
    ./configure
    make CFLAGS="${CFLAGS:-} -std=gnu17"
) >&2
install -m 0755 "$uv" "$uvx" "$fuzz_source/src/fuzz" "$runtime/bin/"
install -m 0644 "$fuzz_source/src/fuzzlib" "$runtime/bin/fuzzlib"
cp -RP -- "$python_home" "$runtime/python"
cp -RP -- "$prob" "$runtime/prob"
install -m 0755 "$node_home/bin/node" "$runtime/node/bin/node"
cp -RP -- "$node_home/lib/node_modules/npm" "$runtime/node/lib/node_modules/npm"
ln -s ../lib/node_modules/npm/bin/npm-cli.js "$runtime/node/bin/npm"
ln -s ../lib/node_modules/npm/bin/npx-cli.js "$runtime/node/bin/npx"
install -m 0644 "$node_home/LICENSE" "$runtime/licenses/node-LICENSE"
curl --fail --silent --show-error --location --max-time 60 \
    "https://raw.githubusercontent.com/Spivoxity/fuzz/$fuzz_ref/README.md" \
    -o "$runtime/licenses/fuzz-README.md"
for notice in LICENSE-APACHE LICENSE-MIT; do
    curl --fail --silent --show-error --location --max-time 60 \
        "https://raw.githubusercontent.com/astral-sh/uv/$uv_version/$notice" \
        -o "$runtime/licenses/uv-$notice"
done

isolated=(env -i "HOME=$work/home" "TMPDIR=$work/tmp"
    "PATH=$runtime/bin:$runtime/node/bin:/usr/bin:/bin" LC_ALL=C)
uv_env=("${isolated[@]}" "UV_PYTHON=$runtime/python/bin/python3.13" UV_PYTHON_DOWNLOADS=never
    "UV_CACHE_DIR=$runtime/cache/uv" "UV_PROJECT_ENVIRONMENT=$work/venv" UV_LINK_MODE=copy
    PYTHONDONTWRITEBYTECODE=1)
"${uv_env[@]}" uv --no-config --directory "$repo" sync --locked --extra dev >&2
# The docstring gate invokes pydoclint in uvx's separate tool environment.
"${uv_env[@]}" uv --no-config --directory "$repo" run --locked \
    python tools/check_python_docs.py docstrings src/ >&2
# Do not cache the editable wheel, which is tied to the builder's checkout.
for sdists in "$runtime"/cache/uv/sdists-v*; do
    rm -rf -- "$sdists/editable"
done
for tool_env in "$runtime"/cache/uv/archive-v*/*/pyvenv.cfg; do
    if [[ -f $tool_env ]]; then
        rm -rf -- "${tool_env%/*}"
    fi
done
find "$runtime/cache/uv" -name .lock -type f -delete

(
    cd "$work"
    "${isolated[@]}" "npm_config_cache=$runtime/cache/npm" npm_config_yes=true \
        npm_config_ignore_scripts=true npm_config_audit=false npm_config_fund=false \
        npm_config_update_notifier=false \
        npx markdownlint-cli2 --version >&2
)
rm -rf -- "$runtime/cache/npm/_logs"
rm -f -- "$runtime/cache/npm/_update-notifier-last-checked"

LC_ALL=C tar --sort=name --format=gnu --mtime=@0 --numeric-owner \
    --owner=0 --group=0 --hard-dereference -C "$runtime" -cf - bin cache licenses node prob python \
    | gzip -n > "$work/runtime.tar.gz"
archive=$output/z-spec-linux-amd64-v1.tar.gz
staged=$(mktemp "$output/.z-spec-linux-amd64-v1.XXXXXX")
install -m 0644 "$work/runtime.tar.gz" "$staged"
mv -T -- "$staged" "$archive"
sha256sum "$archive"
