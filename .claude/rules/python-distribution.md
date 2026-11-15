---
paths:
  - "pyproject.toml"
  - "Makefile"
  - ".github/**"
---

# Distribution Standards

## PL-DI-1: PyPI Publishing

**Statement**: All Python packages publish to PyPI via automated `release.yml`
workflow triggered by tag push (`v*`). Pipeline: build → TestPyPI → test-install
→ PyPI. TestPyPI failure blocks production publish.

**Criterion**:
- Pass: `.github/workflows/release.yml` exists with the four-stage pipeline
- Fail: manual `twine upload`; no TestPyPI gate

**Tooling**:
- Check: `test -f .github/workflows/release.yml`
- `uv build && uvx twine check dist/*` — local validation before tag

## PL-DI-2: Trusted Publishing

**Statement**: Authentication uses OIDC trusted publishing — no tokens or secrets.
Configure each package on both pypi.org and test.pypi.org with owner `punt-labs`,
the repo name, workflow `release.yml`, and environment `release` or `testpypi`.

**Criterion**:
- Pass: no PyPI tokens in secrets; OIDC configured on both registries
- Fail: `PYPI_TOKEN` in GitHub secrets; manual upload

**Tooling**:
- Verify: GitHub Settings → Environments → `release` and `testpypi` exist

## PL-DI-3: Build Validation

**Statement**: Before release, verify the built wheel with `twine check`. The
build must include `py.typed` marker and all package data.

**Commands**:
```bash
uv build
uvx twine check dist/*
```

**Criterion**:
- Pass: `twine check` reports PASSED; wheel contains py.typed
- Fail: twine warnings about missing metadata; py.typed absent from wheel

**Tooling**:
- `make build` target must run build + twine check

## PL-DI-4: .mcpb Bundles for Claude Desktop

**Statement**: MCP server projects also distribute as `.mcpb` bundles for
Claude Desktop. The bundle is built during release and attached to the GitHub
release. `manifest.json` at repo root defines bundle metadata.

**Criterion**:
- Pass: projects with MCP servers have `manifest.json`; `.mcpb` on GitHub release
- Fail: MCP server project with no desktop distribution path

**Tooling**:
- Check: `test -f manifest.json` for MCP server projects

## PL-DI-5: Version Source of Truth

**Statement**: `pyproject.toml` `version` is the single source of truth. All
mirrors (`plugin.json`, `manifest.json`, `__init__.py`, `install.sh` VERSION pin)
must match. Version bump is a single operation that updates all mirrors.

**Criterion**:
- Pass: all version references agree; `punt release` handles bumping
- Fail: version mismatch between pyproject.toml and plugin.json

**Tooling**:
- `punt audit` checks version sync across files

## PL-DI-6: Local Depot for Dev Iteration

**Statement**: Cross-project wheel sharing uses the `.depot/` directory at the
meta-repo root. After changing a library that others depend on, run `make depot`
to build the wheel and place it in `.depot/`. Consumer projects resolve local
wheels via `uv.toml` with `find-links = ["../.depot"]` (gitignored, dev-only).

**Criterion**:
- Pass: `make depot` target exists; `uv.toml` has find-links
- Fail: manual wheel copying; editable installs for cross-project testing

**Tooling**:
- `.bin/depot-sync.sh` — rebuild all projects in dependency order
- `.bin/depot-status.sh` — list depot contents
