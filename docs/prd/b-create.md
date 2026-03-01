# PRD: /z-spec:b-create

## Problem

Z specifications use LaTeX markup and declarative predicates, which makes them
readable and mathematically precise but not directly executable. When users want
to move from specification to implementation, B-Method provides a natural stepping
stone: same mathematical foundations, but with an executable substitution language
and a first-class refinement chain (Machine -> Refinement -> Implementation).

Today, users must manually translate Z constructs to B syntax. The mapping is
mechanical (given sets -> SETS, schema predicates -> INVARIANT, operations ->
substitutions) but tedious and error-prone. There is no command to create a B
machine from scratch or translate an existing Z spec.

## Solution

A new `/z-spec:b-create` command with two modes:

1. **Description mode** --- create a B machine from a natural language description
   (same UX as `/z-spec:code2model` but targeting `.mch` output)
2. **Translation mode** --- translate an existing Z spec (`.tex`) to an equivalent
   B machine, applying the Z-to-B mapping rules from `reference/b-machine-patterns.md`

Both modes produce a `.mch` file in `specs/` and type-check it with `probcli`.

## Scope

### In Scope

- New `commands/b-create.md` and `commands/b-create-dev.md` skill prompts
- Description-to-machine generation with probcli validation
- Z-to-B translation for `.tex` files
- `specs/` directory creation and `.gitignore` updates
- Updates to `commands/help.md` and `README.md`

### Out of Scope

- Automatic refinement generation (that is `/z-spec:b-refine`)
- B-to-Z reverse translation
- Atelier B or other B tool integration (probcli only)
- Implementation machine (`.imp`) generation

## User Workflow

```text
/z-spec:b-create A counter with increment and reset       # From description
/z-spec:b-create docs/counter.tex                         # Translate Z to B
/z-spec:b-check specs/counter.mch                         # Type-check
/z-spec:b-animate specs/counter.mch                       # Animate
/z-spec:b-refine specs/counter.mch                        # Create refinement
```

## Success Criteria

- Description mode produces a syntactically valid `.mch` file that passes
  `probcli Machine.mch -init`
- Translation mode correctly maps Z given sets, free types, state schemas,
  init schemas, and operations to their B equivalents
- Frame conditions are dropped (implicit in B)
- `ZBOOL` is mapped to native B `BOOL` with `TRUE`/`FALSE`
- Output file is placed in `specs/` with appropriate `.gitignore` entries
