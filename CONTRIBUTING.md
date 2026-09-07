# Contributing

Quality gates, in order:

```bash
uv sync
```

```bash
make lint
```

```bash
make type
```

```bash
make test
```

```bash
make check
```

```bash
make uat
```

`make lint` runs ruff check, ruff format --check, markdownlint, and
`check-rulesync` (verifies `AGENTS.md`/`CLAUDE.md` are generated from
`.rulesync/rules/*.md` with no drift, and that `AGENTS.md` stays under
codex's byte cap). `check-rulesync` shells out to `npx rulesync`, so it
needs `npx` on `PATH`.
`make type` runs mypy, pyright, and fuzz on every spec in `examples/`.
`make test` runs pytest and probcli on every spec in `examples/`.
`make check` runs lint, type, test, and the OO/coupling/suppression ratchets —
the full gate that must pass before every commit.
`make uat` builds the wheel and installs the CLI for acceptance testing.

Contributor content — the dev/prod plugin swap, release flow, and project
layout — is in [`docs/development.md`](docs/development.md). The three-loop
development process (backlog → PR → mission) is in
[`docs/WORKFLOW.md`](docs/WORKFLOW.md). The five-tier testing pyramid is in
[`TESTING.md`](TESTING.md).
