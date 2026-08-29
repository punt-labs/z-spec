---
description: Show Z specification plugin help and quick reference
---

# Z Specification Plugin Help

Run this as an interactive getting-started flow. Do not display the
material below as a static document — the goal is for the user to leave
this conversation holding a fuzz-clean, model-checked Z specification of a
problem they actually have, not a page they scrolled past.

## Getting Started: Model Your Own Problem

Walk the user through these steps in order. Do not skip ahead to the
command table below until this path is complete or the user asks for it
directly.

### 1. Find the stateful system

If the user's request already names a system to model, use it. Otherwise
ask: *"What's a stateful system you'd like to model? Something with data
that changes over time and rules about what states are valid — a job
queue, a login session, a library's lending records, an inventory, a
workflow with stages."* One or two sentences from the user is enough to
start; `/z-spec:code2model` will ask follow-up questions if the
description is ambiguous.

### 2. Draft the specification

Run `/z-spec:code2model <their description>`. This writes a first `.tex`
spec to `docs/` with given sets, a state schema, an `Init` schema, and a
few operations — the raw material, not a finished spec.

### 3. Type-check it

Run `/z-spec:check <the file>`. fuzz will very likely report errors on a
first draft — that is normal, not a failure. Fix each one and re-run until
`/z-spec:check` reports `OK`. This loop, not the first draft, is where the
spec actually gets built.

### 4. Model-check it

Run `/z-spec:test <the file>`. probcli animates the spec and explores its
reachable states. If it reports a counter-example, that is the model
telling you something true about the specification as written — walk the
user through what the counter-example means and fix the spec (an
invariant, a precondition, a bound) rather than the report.

### 5. Show them what they have

Once `/z-spec:test` passes clean, tell the user plainly: they now have a
formal, type-checked, model-checked specification of their own system.
Point to natural next steps, only as options, not as required reading:

- `/z-spec:partition` — derive test cases from the spec
- `/z-spec:model2code` — generate code and tests from it
- `/z-spec:audit` — check existing test coverage against it
- `/z-spec:prove` — generate proof obligations, if the invariants matter enough to prove

## Learning Z Notation Itself

The path above teaches the *toolchain* — it assumes just enough Z to read
what `/z-spec:code2model` writes. To learn the *notation* — given sets,
free types, `\Delta`/`\Xi`, schema calculus — from first principles, use
the separate **Tutorial** entry in the lux right-click menu (or the
`browse` tool), which walks a progressive lesson series with a running
example. Don't re-teach notation here; point to it.

## Reference

For syntax and ProB-compatibility detail, consult these rather than
memorizing them:

| File | Contents |
|------|----------|
| `reference/z-notation.md` | Z notation syntax and symbols |
| `reference/schema-patterns.md` | Common schema patterns |
| `reference/latex-style.md` | LaTeX formatting guidelines |
| `reference/probcli-guide.md` | ProB CLI options and usage |
| `reference/test-patterns.md` | Test assertion patterns by language |
| `reference/lean4-patterns.md` | Z-to-Lean 4 translation patterns |
| `reference/b-notation.md` | B-Method notation syntax and types |
| `reference/b-machine-patterns.md` | B machine patterns and Z-to-B translation |

## Command Reference

| Command | Description |
|---------|--------------|
| `/z-spec:setup` | Install and configure fuzz and probcli |
| `/z-spec:doctor` | Check Z specification environment health |
| `/z-spec:code2model [focus]` | Create or update a Z specification from codebase |
| `/z-spec:check [file]` | Type-check a specification with fuzz |
| `/z-spec:test [file]` | Validate and animate with probcli |
| `/z-spec:partition [spec] [--code [language]] [--operation=NAME] [--json]` | Derive test cases from spec using TTF tactics |
| `/z-spec:model2code [spec] [lang]` | Generate code and tests from a Z specification |
| `/z-spec:prove [spec] [--obligations=all\|init\|preserve] [--no-mathlib]` | Generate Lean 4 proof obligations from spec |
| `/z-spec:contracts [spec] [lang] [--invariants-only] [--wrap]` | Generate runtime contracts (pre/post/invariant) from spec |
| `/z-spec:oracle [spec] [lang] [--sequences N] [--steps N]` | Property-based testing with Lean model as oracle |
| `/z-spec:refine [spec] [lang] [--lean] [--generate-abstraction]` | Verify code refines spec via abstraction function |
| `/z-spec:audit [spec] [--json]` | Audit test coverage against spec constraints |
| `/z-spec:elaborate [spec] [design]` | Enhance spec with narrative from design docs |
| `/z-spec:cleanup [dir]` | Remove TeX tooling files (keeps .tex and .pdf) |
| `/z-spec:help` | Run this getting-started flow |

### B-Method Commands

| Command | Description |
|---------|--------------|
| `/z-spec:b-create [description or file.tex]` | Create a B machine or translate Z spec to B |
| `/z-spec:b-check [machine.mch]` | Type-check a B machine with probcli |
| `/z-spec:b-animate [machine.mch]` | Animate and model-check a B machine |
| `/z-spec:b-refine [machine.mch] [refinement.ref]` | Create or verify a B refinement |

## Automatic TeX File Management

`/z-spec:code2model`, `/z-spec:check`, and `/z-spec:test` automatically
copy `fuzz.sty` and Metafont files to `docs/` if missing, and add the
matching patterns to `.gitignore`. Run `/z-spec:cleanup` to remove these
tooling files when done — your `.tex` source and `.pdf` output are
preserved.

## Requirements

**Platform**: macOS or Linux only (Windows not supported)

**Tools**:

- **fuzz**: <https://github.com/Spivoxity/fuzz>
- **probcli**: <https://prob.hhu.de/w/index.php/Download>
- **lean** (optional): <https://lean-lang.org/install/> (for `/z-spec:prove`, `/z-spec:oracle`, `/z-spec:refine --lean`)

Set probcli path: `export PROBCLI="$HOME/Applications/ProB/probcli"`

Run `/z-spec:doctor` to check what's already installed, or `/z-spec:setup`
to install what's missing.

## Start Now

Ask the user directly: **"What's a stateful system you'd like to model?"**
Then run the five steps above against their answer — don't wait for them
to ask a follow-up question first.
