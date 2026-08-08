# Verification tiers for a repository that is half program, half prompt

Status: Proposed
Date: 2026-08-08
Author: rmh
Bead: z-spec-srr
Scope: z-spec as the worked example; §13 states which conclusions generalise
and what they change in punt-kit.

## 1. What z-spec actually ships

Measured on this tree:

| Body of shipped behaviour | Size | Gated by |
|---|---|---|
| Python engine, `src/punt_zspec/` | 6,099 lines across 52 modules | `make check` tiers 1–4 |
| Command prompts, `commands/*.md` (21 prod) | 8,750 lines / 34,513 words / 255,116 bytes | `check-dev-commands`, plus `tests/commands/test_prompt_contracts.py` |
| `-dev` twins of the same | another 8,750 lines | `check-dev-commands` |
| Z corpus, `examples/*.tex` | 8 specs | `make type` + `make test` |

The largest single body of behaviour this repository ships is not the Python.
It is 255 KB of natural-language program executed by a language model, and
until PR #97 nothing in the pyramid touched it. The one gate that named the
directory, `check-dev-commands` (`Makefile:63`), asserts each `-dev` twin
*matches* its prod source. Two identical copies of a wrong protocol satisfy it
perfectly; it tests synchronisation, not correctness.

The defect that prompted this design is the proof. `commands/oracle.md`
specified a wire protocol in which a rejected operation and a no-op success
were byte-identical, so the property-based driver could not assert the one
property the harness exists for. `make check` was green throughout and always
would have been.

`tests/commands/test_prompt_contracts.py` (PR #97) closed the cheap half: 48
deterministic cases asserting that a document specifying a protocol cannot
contradict the worked examples of that protocol embedded in the same document.
It costs nothing and it would have failed against the pre-fix files. It cannot
prove the prompt makes a model emit conforming Lean. Nothing does, for any of
the 21 commands.

This document defines what would, what it costs, what it cannot claim, and
where it sits in a pyramid whose top tier is currently one sentence:
`PL-TT-1` names "4. SDK — End-to-end with Claude (costs money), ~30s, Runs in
CI: No" (`../.claude/rules/python-testing.md`) and stops.

## 2. The framework, adopted

This design takes its classification wholesale from punt-labs' own five-level
taxonomy, [The Verification Gap](https://www.punt-labs.com/blog/the-verification-gap)
(local source: `../public-website/src/content/blog/the-verification-gap.md`),
rather than inventing a parallel one. Its levels, and its own summary of what
each level's oracle can claim:

| Level | Control | Oracle | Gap |
|---|---|---|---|
| 1 Fully deterministic | code only | exact match | none |
| 2 Deterministic + narrow ML | code calls a classifier | precision/recall threshold | measurement |
| 3 Deterministic scaffold + LLM | your code calls the LLM | structural + LLM judge | oracle |
| 4 LLM orchestrator + tools | the LLM calls your code | tool contracts + trajectory scoring | orchestration |
| 5 Fully agentic | the LLM is the program | rubric only | fundamental |

I take three positions on it. Two are extensions; one is a disagreement.

### 2.1 Classify per surface, not per tool

The post's "Built at vs Designed for" table classifies whole tools
(blog:207–213): Quarry, Biff, Vox, Lux and Punt Kit are "built at L1, designed
for L4"; PR/FAQ, langlearn-tts and Dungeon are "L4 applications". z-spec fits
neither row. It is built at L1 *and* at L4, in one repository, shipped in one
wheel and one plugin: `src/punt_zspec/` is deterministic Python with an exact
oracle, and `commands/` is 21 agentic programs with none. A single label for
the tool would be a lie in one direction or the other.

This is not a z-spec quirk. It is the general case for any repository that
ships a Claude Code plugin alongside a package — which, at punt-labs, is
quarry, vox, biff, lux and z-spec. **Classify each client surface separately.**
The "built at / designed for" pair then becomes a property of a surface, and
the tool inherits no level at all.

### 2.2 The oracle is a second axis, and it is the one that picks the tier

The five levels are defined by control flow: who calls whom. That is the right
definition of the thing they name, and the post's phase transition at 3→4 —
the inversion of control — is correctly identified as the biggest hit to what
you can *prove*.

But control flow is not what selects a verification method. What selects it is
the strength of the oracle available for the *artifact* the surface produces,
and the two axes come apart in both directions:

- `/z-spec:oracle` is Level 4 by control (the model drives, calling `lean`,
  `lake`, `Write`) and its artifact is decided **exactly** — a Lean program
  either builds or does not, and a binary either speaks the NDJSON protocol or
  does not.
- `/z-spec:elaborate` is also Level 4 by control (it reads files and writes
  them) and its artifact is mostly prose. Only a judge can score it.

So a second axis, three values, and it is this axis the tier selection reads:

| Oracle | Meaning | Example in this repo |
|---|---|---|
| **Exact** | a deterministic checker exists, is installed, and decides the whole artifact | `fuzz -t` on a `.tex`; `lake build` on `proofs/`; `partition_from_dict` on a report (`src/punt_zspec/commands/partition.py:66`) |
| **Structural** | deterministic predicates decide part of it; the rest is undecided | "the emitted Swift parses"; "every declared operation appears in the generated file" |
| **Rubric** | only a judge, human or model, can score it | the narrative in an elaborated spec; `commands/help.md` |

**Rule: the verification method is chosen by the oracle strength of the output,
not by the control level of the producer.** §5 turns this into a design
obligation; §11 uses it to decide which commands earn the expensive tier.

### 2.3 Where I disagree: epistemic loss and test cost are different orderings

The post ranks the levels by how much verification *can claim*. A standard for
a shipping team also has to rank them by what a test *costs*, and the two
orderings do not agree.

By epistemic loss the sharpest step is 3→4. By test cost the sharpest step is
2→3: that is where a test stops being a function you can run in a loop for free
and becomes a network call against a metered, non-reproducible service. Every
tier above it needs a budget, a rate policy, and a decision about what a single
red result means.

Conflating the two orderings is, I think, why this tier is universally skipped.
Teams read "the gap widens at 4" and reach for trajectory scoring, when the
thing that actually stopped them was that at level 3 the test suite acquired a
bill. Naming the cost transition separately is the difference between a tier
that gets built and one that stays a sentence in a rules file. §7 and §8 are
written to that transition.

## 3. Every surface, classified

### 3.1 The Python engine — `src/punt_zspec/` (6,099 lines)

Level 1, exact oracle, zero gap. Nothing in it calls a model. `parser.py`,
`report.py`, `manifest.py`, `atomic_file.py`, `claude_md.py`, `gate.py`,
`commands/*.py`, `types/*` are ordinary deterministic Python covered by tier 1.

The verification-relevant fact is that this is the layer to which work should
migrate. Every capability that lives here is a verification problem that no
longer exists.

### 3.2 The binary wrappers — `fuzz.py`, `prob.py`

Level 1. They wrap tools that are themselves deterministic; a fuzz type error
or an absent `probcli` is normal input, not an exception. `TESTING.md` already
requires success / tool-absent / tool-failed coverage on each, and
`tests/test_fuzz.py` and `tests/test_prob.py` patch `subprocess.run` against
captured output.

### 3.3 The Z corpus — `examples/*.tex` (8 specs)

Level 1 data with an exact oracle, twice over: `fuzz -t` decides types
(`Makefile:31-33`) and `probcli -model_check` explores the reachable state
space (`Makefile:43-54`). This is the strongest-verified thing in the
repository, and it is worth noting why: the artifact is a mathematical object
and its checker is on disk. That is the condition §6 asks whether the prompts
can be brought into.

### 3.4 The CLI and MCP surfaces — `__main__.py`, `server.py`

Level 1, built at L1 and designed for L4 consumption — the post's building-block
row, exactly. `tests/commands/test_parity.py` asserts the two surfaces resolve
to one `Command`; `tests/e2e/test_installed_cli.py` and
`tests/e2e/test_installed_mcp.py` drive the installed artifact as a subprocess
and over stdio.

### 3.5 The lux rendering — `display.py`, `applet.py`, `browser.py`, `lux/`

Level 1 by control, but its oracle is weaker than the rest of the engine: the
Hub's introspection API decides that a scene exists and holds elements, and
nothing decides that the scene *renders*. `TESTING.md` records the divergence
("a scene can hold 838 elements and render an empty pane"). This is a
Structural oracle on a Level 1 surface — further evidence that the two axes are
independent — and it is why tier 5 is a human at a screen.

### 3.6 The 21 command prompts — `commands/*.md`

Twenty of the 21 are Level 4 by control: a model drives, calling deterministic
tools — including `elaborate.md`, which reads a spec and a design document and
writes an elaborated one. `help.md` is the degenerate case: it calls nothing and
emits a static reference table, so its "program" is a recitation of its own
text. What differs across the 21, and what matters, is the oracle on the
artifact each produces.

| Command | Lines | Words | Artifact | Checker invoked in the prompt | Oracle |
|---|---|---|---|---|---|
| `oracle` | 1,601 | 6,226 | Lean executable + NDJSON protocol + PBT driver | `lake build oracle` (`oracle.md:344`, `:1225`) | **Exact** |
| `refine` | 1,536 | 5,465 | Lean refinement obligations + abstraction fn | `lake build` (`refine.md:932`) | **Exact** |
| `contracts` | 939 | 3,989 | runtime contracts in Swift/TS/Python/Kotlin | **none** — `allowed-tools` is `Bash(fuzz:*), Bash(which:*)` (`contracts.md:4`) | Structural |
| `prove` | 874 | 3,408 | Lean 4 project + proof obligations | `lake build` (`prove.md:572-599`) | **Exact** |
| `code2model` | 555 | 2,198 | `.tex` Z specification | `fuzz -t` (`code2model.md:237-246`) | **Exact** |
| `partition` | 548 | 2,800 | TTF partition report (JSON) | `save_partition_report` → `partition_from_dict` | **Exact** (schema) |
| `setup` | 376 | 1,161 | an installed toolchain | `which` probes | Structural |
| `model2code` | 349 | 1,121 | source code in four languages | **none** — `allowed-tools` is `Bash(fuzz:*), Bash(which:*)` (`model2code.md:4`) | Structural |
| `b-create` | 314 | 983 | `.mch` B machine | `probcli` (`b-create.md:268-282`) | **Exact** |
| `audit` | 284 | 1,344 | coverage audit report (JSON) | `save_audit_report` → schema | **Exact** (schema) |
| `elaborate` | 260 | 874 | elaborated `.tex` + narrative | `fuzz -t` (`elaborate.md:153-160`) | Exact on the Z blocks, Rubric on the prose |
| `b-refine` | 194 | 755 | `.ref` refinement machine | `probcli` | **Exact** |
| `b-animate` | 183 | 569 | animation report | `probcli` | **Exact** |
| `help` | 165 | 921 | prose | none | Rubric |
| `doctor` | 116 | 508 | status table | `zspec doctor` + shell probes | **Exact** |
| `test` | 102 | 497 | probcli report | `zspec test` | **Exact** |
| `cleanup` | 95 | 274 | file removals | none | Structural |
| `b-check` | 83 | 341 | type-check report | `probcli` | **Exact** |
| `check` | 80 | 623 | fuzz report + animation hints | `zspec check` | **Exact** on the report, Rubric on the hints |
| `enable` | 49 | 240 | marker + `@`-import line | `zspec enablement` | **Exact** |
| `disable` | 47 | 216 | marker removal | `zspec enablement` | **Exact** |

Two findings fall straight out of the table and both are actionable now.

**Finding 1.** `model2code.md` and `contracts.md` — 1,288 lines and 5,110 words
between them — generate compilable source code in four languages and are
*tool-restricted so they cannot compile it*. Both declare
`allowed-tools: Bash(fuzz:*), Bash(which:*), Read, Glob, Grep, Write`
(`model2code.md:4`, `contracts.md:4`). `fuzz` type-checks Z, not Swift. There
is no step in either prompt that runs a compiler, and no permission to. Every
other artifact-producing command in the corpus runs its checker; these two are
the exceptions.

**Finding 2.** For the commands that *do* run their checker, the checker's
result is reported by the model and verified by no one. `prove.md:698` documents
the failure path as "`lake build` fails → show errors, suggest fixes, keep
`sorry` markers" — a build failure is a normal, reported outcome. Nothing
distinguishes "the prompt worked and the proof was hard" from "the prompt
emitted Lean that does not compile", and nothing at all catches a model that
runs `lake build`, reads the errors, and writes that it succeeded. §4 makes
this the load-bearing distinction.

## 4. Where the boundary falls: the result is deterministic, the model is not

The operator's framing is the design's centre, and it resolves to one sentence
per surface: **the artifact is deterministic; its production is not; therefore
every assertion must be made against the artifact, never against the account
the producer gives of it.**

Concretely, for `/z-spec:oracle`:

| On the deterministic side | On the non-deterministic side |
|---|---|
| `proofs/ZSpec/Oracle.lean` exists and `lake build oracle` exits 0 | whether the model chose to generate `Oracle.lean` at all |
| the built binary, given a scripted NDJSON stdin, emits one line per command plus the initial state | which operations the model decided to include |
| every emitted line parses and carries `ok` and `state` (`oracle.md:1151-1167`) | whether the model transcribed the protocol correctly from the prompt |
| a precondition-violating command yields `ok:false`, a `reason`, and a `state` identical to the prior line | whether the model derived the right precondition from the Z schema |
| the generated PBT driver file exists and parses in its target language | whether the driver's generators are well-chosen |

Everything in the left column is a predicate a test can evaluate with no model
in the loop, no judge, and no sampling. Everything in the right column is a
property of a distribution over model outputs, and the only honest statement
about it is a rate with a sample size attached.

The same split, stated generally:

- **Assertions about the artifact** are Level 1 assertions. They are exact,
  free to evaluate, and reproducible. They belong in the highest tier that can
  obtain an artifact.
- **Assertions about the production** are statistical. They have one form:
  "over *n* runs of this prompt against this fixture with this model, the
  artifact satisfied its artifact-assertions *k* times." That is the only claim
  the expensive tier makes, and §8 rules on what may be done with it.
- **The model's own report is not evidence of either.** The prompt tells the
  model to run `lake build` and report; the test runs `lake build` itself.

This is also the answer to why `tests/commands/test_prompt_contracts.py` is
free (§12): a prompt document is an artifact too. Its execution is
non-deterministic; the file on disk is not.

## 5. Push behaviour down the spectrum — as an obligation

The post's first strategy is "push behaviour down the spectrum" (blog:223–225).
Every capability sitting in a prompt that could be deterministic code is a
verification problem that need not exist. Beads `z-spec-uq7`, `z-spec-l05` and
`z-spec-oj3` already ask this of the corpus.

### 5.1 Push the *oracle* down before you push the *behaviour* down

The post applies "push down" to behaviour only. The stronger and much cheaper
move is to apply it first to the oracle.

Moving behaviour from a prompt into code is a restructure: it costs a design,
an implementation, tests, and it changes what the product does. Moving an
artifact from a Rubric oracle to a Structural one, or from Structural to
Exact, is usually a few lines — add a checker invocation, add a required key,
constrain an output format — and it changes only what you can *assert*.

And it must come first, because the oracle strength decides whether the
behaviour pushdown was needed at all. A command whose artifact is decided
exactly does not need its logic moved into Python to be verifiable; it needs a
test that runs the checker. A command whose artifact is prose cannot be
verified however much of its control flow you move.

So, as a rule: **before writing a probabilistic test for an agentic surface,
exhaust the deterministic checks on its artifact.** Every check you add there
is one the expensive tier no longer has to make, at a fraction of the cost and
with none of the sampling.

### 5.2 What descends, concretely

Ordered by ratio of verifiability bought to work required.

**Tier A — oracle pushdown, prompt-only edits.**

1. `model2code.md` and `contracts.md`: widen `allowed-tools` to the target
   language's compiler and add a mandatory build step with an explicit pass
   condition. Buys: an Exact oracle on 1,288 lines of prompt whose artifact is
   currently unchecked, and it buys it for the *user*, on every real run, not
   only in a test. This is the single highest-value change in the document.
2. `elaborate.md`: `:153-160` already runs `fuzz -t`; make the pass condition
   explicit and make a failure block the success report. Elaboration edits a
   type-checked spec; the risk it uniquely carries is breaking one.
3. `code2model.md:244-246` says "fix type errors iteratively" with no
   termination condition and no exit criterion. State one: fuzz-clean, or
   report the remaining errors as a failure. An unbounded repair loop reported
   as success is the same defect class as Finding 2.

**Tier B — behaviour pushdown, engine work.**

1. `partition` (2,800 words) and `audit` (1,344 words) do all TTF decomposition
   and constraint extraction in the model; the Python layer only validates and
   persists the JSON (`src/punt_zspec/commands/partition.py:57-81`). Beads
   `z-spec-l05` and `z-spec-oj3` propose moving the extraction into code. The
   blocker is real and I will not understate it: `parse_spec`
   (`src/punt_zspec/parser.py:192`) yields `ZBlock.predicates` as a raw string
   (`src/punt_zspec/types/spec.py:26`), not a parsed predicate. Deterministic
   partition generation needs a Z predicate parser that does not exist. §14
   names the spike that would settle whether it is worth building.
2. `check.md:44-75` — the animation-hint checklist is six syntactic patterns
   over LaTeX ("unbounded `\finset` over a given set", "underscored free type
   constructors", "`\mu` in an operation schema"). These are lint rules. They
   are stated as a checklist for a model to apply by eye, and applied by eye
   they are neither complete nor reproducible. They belong in `parser.py` as a
   deterministic linter with an Exact oracle, and `check.md` shrinks to
   reporting its output. This is the clearest single case in the corpus of
   behaviour that is already fully specified and merely mis-housed.
3. `setup.md` (1,161 words) is an installer written in prose. Installers are
   Level 1 work. It belongs behind `z-spec setup`, a CLI verb, tested as
   subprocess code.

Neither tier is in scope for this design; both are named so the implementation
mission for the expensive tier is not asked to test capabilities that should
have been deleted from the prompt first.

## 6. Does z-spec's own thesis apply to z-spec?

The post's second strategy is "formalize the specification" (blog:227–229):
replace the natural-language prompt with Z, TLA+ or B — a mathematical object
admitting type-checking, animation and model-checking — so that "the spec
becomes a contract that the agentic output is tested against, not a suggestion
it may or may not follow." That is z-spec's product thesis stated in one
sentence. z-spec's own primary artifact is 255 KB of natural-language prompt,
unverified. The question is whether the thesis applies to the tool itself.

The answer is yes for one part of a prompt, no for another, and the boundary
between them bounds the product's claim as much as it bounds this design.

### 6.1 A command prompt has three parts, and they are not alike

Taking `commands/oracle.md` as the specimen:

**Part 1 — control flow and preconditions.** `oracle.md:31-68`: verify `lean`
and `lake` are on `PATH`; if absent, stop with this message; verify
`proofs/lakefile.toml`, `State.lean` and `Operations.lean` exist; if incomplete,
stop with that message; check the Lean major version. This is a state machine
over a finite set of conditions. It is specifiable in Z — and that is exactly
the wrong thing to do with it, because it is also *implementable*. Writing a Z
schema for it and leaving the prose in the prompt gets you a specification
nobody checks against a program nobody can check. The right disposition is §5's
Tier B: move it into Python, where the Z model would be a model of the code and
this repository's existing pipeline (`fuzz` then `probcli`) verifies it, and
where `WORKFLOW.md`'s `statefulClass` rule already mandates the Z model before
the implementation. So: Z applies, and its payoff is deletion from the prompt.

**Part 2 — the output contract.** `oracle.md:1135-1181` and
`docs/prd/z-oracle.md:60-92`: an NDJSON grammar plus an invariant. Every
oracle→harness line carries `ok` and `state`; `ok:false` means the precondition
did not hold; on `ok:false` the state is unchanged; `reason` is diagnostic and
not to be parsed. This is a formal object and nothing else. It is a state
schema, an initialisation schema, and two operation schemas — the accepting
case with a `\Delta` and the rejecting case with a `\Xi` frame and an output
verdict. It is precisely the kind of thing the tool exists to check.

And it is where the bug was. The defect PR #97 fixed is, stated in Z, the
absence of an output variable distinguishing two operations with identical
after-states. In a Z schema that omission is visible on inspection and provable
by animation: two operations, same `\Xi State`, no distinguishing output, so no
observer can tell them apart. It did not need a model to catch. It needed the
contract written as a mathematical object instead of as prose in the middle of
a 1,601-line document.

**Part 3 — the elicitation.** "Derive equivalence classes using TTF tactics."
"Generate idiomatic Kotlin." "Scan the specification for patterns that pass
fuzz but cause probcli animation failures." This is not a specification of a
computation. It is a *stimulus*, chosen because it empirically produces a
useful distribution of outputs from a particular set of weights. Formalising it
is a category error: the formalisable thing is the output contract, which is
Part 2, and the prompt text is an attempted implementation of it. You cannot
type-check an implementation into existence.

### 6.2 What to do about it: `examples/oracle-protocol.tex`

The concrete recommendation, and the one piece of z-spec self-application I
would actually build:

**Write the oracle wire protocol as a Z specification at
`examples/oracle-protocol.tex`, and let `make check` type-check and
model-check it like every other spec in the corpus.** It must live in
`examples/` and nowhere else: that is the directory the `SPECS` wildcard
(`Makefile:12`) sweeps into the tier 2 and tier 3 gates, so putting it there
costs one file and no Makefile change. It is small — one state schema for the oracle's view of
the model state, an init schema, `AcceptOp` with `\Delta` and `ok! = ztrue`,
`RejectOp` with `\Xi`, `ok! = zfalse` and a `reason!` output. It obeys the
repo's ProB conventions without strain: `ZBOOL ::= ztrue | zfalse` for the
verdict, bounded state for animation, flat schemas.

What that buys, in order of value:

1. **The contract becomes checkable by the tool that ships it.** `fuzz -t`
   decides its types; `probcli -model_check` explores it. The repository's
   thesis is applied to the repository's own most defect-prone artifact.
2. **`tests/commands/test_prompt_contracts.py` gets an authority.** Its
   assertions are currently hand-written against prose
   (`test_prompt_contracts.py:107-138` requires `ok`, `state`, and a `reason`
   on rejections). With the Z spec in place, those assertions are a
   transcription of a model-checked schema, and the docstring cites it. The
   test does not change; what changes is that it stops being one engineer's
   reading of a paragraph.
3. **The prompt and the PRD get a single source.** The protocol is currently
   stated twice, in `commands/oracle.md:1151-1167` and
   `docs/prd/z-oracle.md:60-92`, plus once more in `commands/oracle-dev.md`.
   Three prose copies is how the first divergence happened.

I would like the prompt-contract assertions to be *generated* from the Z spec
rather than transcribed. They cannot be, today: `parse_spec` yields predicates
as raw LaTeX text (`parser.py:192`, `types/spec.py:26`), so nothing can turn
`ok! = zfalse` into a JSON key assertion. §14 records this as an open question
with the spike that would answer it. Transcription with a cited authority is
the currently-available form and it is a large improvement on transcription
with none.

### 6.3 What this bounds

The honest statement of the product's claim, which this design should not
overstate and which the marketing should not either:

**Z formalises the contract. It does not formalise the elicitation.** z-spec
can make an agentic system's *output* checkable against a mathematical model;
it cannot make the agent correct, and no amount of specification will. That is
the same claim the post makes for Cryptd — "the LLM narrates the story; the
spec verifies the state transitions" (blog:229) — and it is a real claim, worth
making, and smaller than "formal methods close the verification gap."

The residue is exactly the expensive tier. Once the contract is formal and the
checker exists, the only remaining question is a rate: how often does this
prompt, against this fixture, with this model, produce an artifact the checker
accepts. That question has no formal answer, and §7 onward is about how to buy
a useful approximation of one.

## 7. The tiers

z-spec has five tiers today (`TESTING.md`). I add one, numbered 6 because it is
the most expensive and makes the smallest claim. It sits above the acceptance
flight for the same reason the acceptance flight sits above `make check`.

`PL-TT-1`'s tier 4 is named after its transport ("SDK"). That is part of why it
is empty guidance: a transport is not a claim. Name it for what it asserts —
**elicitation conformance**: does the shipped prompt, executed by a live model
against a fixture, produce an artifact its checker accepts.

| # | Tier | Asserts | Cost | Cannot catch | `make check` | CI | Marker |
|---|---|---|---|---|---|---|---|
| 1 | Unit + document conformance | each module in isolation; each prompt document is internally consistent and its embedded examples satisfy the contract | seconds, $0 | that any prompt elicits anything; packaging faults | yes | `test.yml` `unit` | — |
| 2 | Spec type-check | every `examples/*.tex` is fuzz-clean | seconds, $0 | semantics the type system admits | yes | `test.yml` `specs` | — |
| 3 | Spec model-check | probcli finds no counterexample within the bound | minutes, $0 | anything outside `DEFAULT_SETSIZE`/`MAX_OPERATIONS` (`Makefile:46-49`) | yes | `test.yml` `specs` | — |
| 4 | Surface parity | the CLI verb and the MCP tool resolve to one `Command` with one option set | ms, $0 | whether either surface behaves correctly | yes | `test.yml` `unit` | — |
| 5 | Acceptance — subprocess and human | the installed wheel's CLI and stdio MCP server answer; the lux window shows what a person would want | subprocess: seconds; human: minutes | anything the human did not run; anything intermittent | no (`make test-e2e`) | `test.yml` `e2e` (subprocess half only) | `e2e` |
| 6 | **Elicitation conformance** | over *n* runs, a live model given the shipped prompt and a fixture produced an artifact its checker accepted *k* times | minutes and real money **per run** | whether the artifact is *good*; behaviour on any other spec; behaviour on any other model version; anything at *n* below the sample size | **no** | **no** — a separate workflow on release and on schedule | `sdk` |

Tier 6, spelled out to the level `PL-TT-1` does not reach:

- **What it asserts.** One statement, with three parameters that must appear in
  the result: *prompt version × fixture × model version → k of n*. A result
  without all three is not a result.
- **What it costs.** `commands/oracle.md` is 47,908 bytes ≈ 12,000 tokens of
  prompt before the model reads a single file. A realistic run also reads the
  fixture spec, reads `proofs/ZSpec/State.lean` and `Operations.lean`, writes
  three or four files, and runs `lake build` — on the order of ten turns with
  growing context, so a few hundred thousand input tokens and tens of thousands
  of output tokens per run, most of the input cacheable because the prompt is
  byte-identical across samples. At Sonnet-class rates that is on the order of
  $1 per run; at Opus-class, several times that. Sixty runs is on the order of
  $100 for one command, one suite execution. **I have not measured this, and it
  must be measured before any *n* is committed to** — §14, item 2.
- **What it cannot catch.** That the generated oracle is *correct* — only that
  it builds and speaks the protocol. That it works on a spec unlike the
  fixture. That it works on the model version users are actually served. And,
  at any *n*, failure rates below roughly `3/n`.
- **Gate.** Not `make check`, not the merge gate. §8 rules on why and on what
  it gates instead.
- **Marker.** `sdk`, added to `[tool.pytest.ini_options] markers`
  (`pyproject.toml:127-129`, which currently declares only `e2e`) and excluded
  from `addopts` the same way `e2e` is (`pyproject.toml:125`).

## 8. Flakiness: the ruling

A model may satisfy a contract on one sample and miss it on the next. This is
the reason the tier is skipped everywhere, so it gets a ruling, not a caveat.

### 8.1 A probabilistic gate must never block a merge

Three independent reasons, each sufficient:

1. **`PL-TT-4` says flaky tests are bugs**
   (`../.claude/rules/python-testing.md`). A sampled gate is flaky by
   construction. Admitting one to `make check` either voids that rule or forces
   retry-until-green, which is the practice `PL-TT-4` exists to forbid.
2. **The merge gate is a conjunction of deterministic predicates**
   (`docs/WORKFLOW.md`, `merge_gate`). Adding a term whose value is a random
   variable makes the gate itself non-deterministic: the same commit passes and
   fails. "CI green on the latest commit" stops meaning anything.
3. **Every push restarts the gate** (`docs/WORKFLOW.md`, invariant 5). A gate
   costing real money per evaluation, multiplied by every push in every review
   cycle, is an unbounded bill for a signal a single sample cannot support.

So: **tier 6 never blocks a merge, and no result of it is ever retried into
green.**

### 8.2 What it is for instead

Three purposes, three run profiles. The sample sizes below use the rule of
three: observing zero failures in *n* trials bounds the true failure rate at
roughly `3/n` with 95% confidence.

| Purpose | When | *n* | Bar | On failure |
|---|---|---|---|---|
| **Prompt-change evidence** | by hand, before a PR that touches `commands/*.md`, per changed command | 10 | zero failures | escalate to the release profile before concluding anything (§8.3) |
| **Release evidence** | on the release tag, before publishing to PyPI and the marketplace | 60 | zero failures → "failure rate under 5%, 95% confidence" | blocks the *release*, not any merge |
| **Drift alarm** | scheduled weekly, and on any model-version change | 30 | compared against the recorded release baseline | files a bead; blocks nothing |

The first profile is the important structural point, and it costs nothing to
adopt because the slot already exists. This repository already has a
non-CI, human-run, pre-PR gate: the acceptance flight
(`docs/testing/manual-tests.md`, `make uat`), required before the PR opens by
`docs/WORKFLOW.md` and by `TESTING.md`'s tier 5. **Tier 6 for prompt changes is
a row in that flight, not a new mechanism.** A PR that edits a command prompt
carries its *k*/*n*, its fixture, and its model version in the PR body, the same
way a PR touching lux carries a screenshot. Discipline enforces it; nothing
mechanical does; and that is the correct treatment for a signal that cannot be
trusted mechanically.

The second is why a release is the right gate: a release is deliberate,
low-frequency and human-initiated, so waiting several minutes and spending real
money is proportionate, and the thing being certified — the artifact users
install — is exactly what tier 6 measures.

### 8.3 Distinguishing a regression from sampling noise

You cannot, from one suite run at *n* = 10. Saying so plainly is more useful
than a threshold that pretends otherwise. The escalation:

1. A failure at the pre-PR profile is **not** a verdict. Record the exact
   input, the model version, and the artifact.
2. Reduce it: rerun at the release profile, *n* = 60, same fixture, same pinned
   model. This is the only step that produces a rate.
3. Classify the outcome, into exactly one of three:
   - **Prompt defect.** The failures share a cause traceable to the prompt text
     — an ambiguous instruction, a missing step, a contradictory example. Fix
     the prompt. Where the defect was decidable from the document, add the
     assertion to tier 1 so it never needs a model again (§12).
   - **Contract defect.** The artifact is defensible and the checker is wrong,
     or the contract is ambiguous. Fix the Z spec (§6.2) and then the prompt.
     This is what the PR #97 bug would have been classified as.
   - **Model variance.** No common cause; failures are diffuse. Then the
     command does not meet the bar at that *n*, and the honest response is to
     record the measured rate as the command's published conformance rate and
     either lower the bar deliberately or narrow the fixture until it is met.
     Not to retry.
4. A clean *n* = 60 after a single pre-PR failure: record it in the drift log
   and proceed. That is a `1/70` observation, consistent with a rate under 5%,
   and treating it as a blocker would be reading noise as signal.

## 9. Determinism controls: what works and what only looks like it

| Control | Reduces variance? | Ruling |
|---|---|---|
| `temperature = 0` | Partly, and it costs external validity | **Do not use.** Greedy decoding is not reproducible on hosted inference — batch composition changes floating-point summation order, and routing is not fixed. More decisively, Claude Code does not serve users at temperature 0, so a suite that pins it measures a distribution nobody runs. Test at the settings users get. |
| Random seed | Unavailable | The Messages API exposes no seed parameter. Verify before implementing; do not design around it. |
| Model version pinning | **Yes**, and it is exactly wrong for one of the three profiles | **Pin two axes, not one** — see below. |
| Prompt caching | **No** — it is an economics control | Use it: the 12,000-token prompt is byte-identical across all *n* samples, so the cache hit rate approaches 1 and dominates the bill. Never claim it as a determinism control. |
| Fixture size | **Yes — the strongest lever available** | Variance in agentic output scales with the number of independent decisions the model makes. Design the fixture as the smallest spec that still exercises the property. §10 specifies it. A small fixture also makes every failure diagnosable, which is what §8.3 step 3 depends on. |
| Assertion coarseness | **Yes, and it is free** | The variance that matters is not variance in the output text but variance in whether the output satisfies the assertion. "`lake build` exits 0" is a coarse predicate over an enormous output space; "the file contains this exact identifier" is a fine one over the same space, and it will flake on formatting choices that are not defects. **Choose the coarsest assertion that still proves the property.** This is a variance control that costs nothing and is routinely overlooked. |

On pinning, and the objection that pinning means the suite stops testing the
model users actually run: that objection is correct, and it is resolved by
noticing that the three profiles in §8.2 want different things.

- **The release profile pins.** Its output is a reproducible, attributable
  claim about a specific artifact: "prompt at commit *c*, fixture *f*, model
  *m*, 60/60." A floating model makes that claim unrepeatable and therefore
  worthless as release evidence.
- **The drift profile floats.** It runs against the default model Claude Code
  actually serves. Its entire purpose is to notice when that has diverged from
  the pinned baseline — which is only observable if one of the two runs is not
  pinned.
- **The pre-PR profile pins**, to the release baseline, because it is asking
  about the prompt change and wants the model held constant.

Two runs, two purposes. Neither alone is sufficient, and the usual failure is
to build only the pinned one and conclude the suite is "stable."

## 10. The assertion target

**Chosen: executed protocol conformance, in three steps, all three asserted.**

Against a fixture spec and a `proofs/` tree produced by `/z-spec:prove`, run
`/z-spec:oracle`, then, with no model in the loop:

1. `lake build oracle` in `proofs/` exits 0.
2. The built binary, fed a scripted NDJSON command sequence on stdin, emits
   exactly one line per command plus the initial state; every line parses as
   JSON and carries both `ok` and `state` (`oracle.md:1151-1160`).
3. The scripted sequence includes one command whose precondition fails. That
   line carries `ok: false`, a non-empty `reason`, and a `state` byte-identical
   to the preceding line's `state` (`oracle.md:1158-1167`,
   `docs/prd/z-oracle.md:80-89`).

Step 3 is the assertion that matters; steps 1 and 2 are the prerequisites that
make it evaluable. Step 3 is exactly the property the shipped bug violated, and
it is the property the whole command exists to establish.

The alternatives, and why each is rejected:

- **"The artifact parses."** Too weak, and demonstrably so: the pre-fix
  `oracle.md` would have passed it. Parse-level checking is already tier 1
  (`test_prompt_contracts.py:89-92`), it is free there, and paying model money
  for it would be a category error.
- **"It compiles."** Necessary, insufficient, and for the same reason: a Lean
  program that emits bare state objects compiles perfectly. Compilation is step
  1, not the target.
- **"It round-trips against a known-good oracle."** Circular as stated. The
  known-good oracle would have to be either generated by the same command —
  which asserts nothing — or hand-written, in which case the hand-written one
  is the fixture and the assertion collapses into step 3. Rejected as an
  independent target because it is not independent.
- **"An LLM judge scores it."** Rejected, and this is the disagreement with the
  post's Level 3 recommendation of "structural + LLM judge" (blog:189). That
  recommendation is right for its own example, where the output is a natural
  language greeting and the property is "is it stereotypical?" — no
  deterministic checker can decide that. It is wrong here. The artifact is a
  Lean program with a wire contract; a compiler and a scripted stdin session
  decide it exactly, for free, reproducibly. Hiring a judge would replace an
  exact predicate with a probabilistic one, add a second oracle gap on top of
  the first, and produce drift scores confounded with drift in the judge.

  The general rule I would put in the standard: **use a judge only when no
  deterministic checker can decide the property, and prefer moving the property
  into a checkable artifact over hiring a judge.** That is §5.1 applied to the
  oracle, and it is the reason the corpus survey in §3.6 leads with "checker
  invoked" rather than "output quality."

**The fixture.** `examples/` has no oracle fixture, which is why the acceptance
flight has no row for the command. Add the smallest spec that exercises step 3:
one given set, one free type, one state schema with two fields and one
invariant, one init schema, one `\Delta` operation with a precondition that can
fail, one `\Xi` query. It must be fuzz-clean and probcli-clean so it joins the
tier 2 and tier 3 gates automatically via the `SPECS` wildcard
(`Makefile:12`) — the fixture for the expensive tier is thereby also covered by
the free ones, which is the correct arrangement.

**The blocker to name.** No Lean toolchain is installed here, and `elan` plus a
Lean 4 toolchain is a multi-minute, several-hundred-megabyte install.
`commands/setup.md` handles it for users. For the test tier it means the tier 6
job is a separate workflow with its own toolchain step, never a job in
`test.yml`, whose `specs` job already carries a fuzz build from source and a
ProB download (`.github/workflows/test.yml:59-95`).

## 11. Which commands earn the tier

The rule, in three conditions, all required:

1. **A checker exists and is installed** for the artifact (Exact oracle, §2.2).
2. **A prompt failure is invisible to every cheaper tier.** If tier 1 can decide
   it from the document, tier 1 owns it (§12).
3. **The blast radius justifies the cost.** An artifact the user carries into
   their own test suite outranks a report they read once.

Applied to the corpus:

**Earns it now — `oracle`.** All three. Its checker exists (`lake`), its
protocol bug is the defect class in question and has already shipped once, and
its artifact is a test harness a user will trust to certify *their*
implementation — the largest blast radius in the corpus. It is also the deepest
prompt at 6,226 words, which is where elicitation failure is most likely.

**Earns it next — `prove`.** Same checker, simpler assertion (the generated
Lean project builds; the obligations that remain undischarged are explicitly
marked, not silently dropped), and `oracle` depends on it, so it shares the
fixture and most of the harness. Phase two.

**Does not earn it, because §5.1 comes first — `contracts`, `model2code`,
`refine`, `b-create`, `b-refine`, `code2model`.** Each produces a checkable
artifact, and for the first two the checker is not even reachable from the
prompt (`contracts.md:4`, `model2code.md:4`). Fix that first. Widening
`allowed-tools` and adding a mandatory build step buys an Exact oracle on every
real user run, at the price of a prompt edit; a tier 6 suite buys a sampled
claim about a fixture, at the price of a toolchain and a budget. Do the cheap
one, then re-ask.

**Does not earn it — `check`, `test`, `b-check`, `b-animate`, `audit`,
`partition`, `doctor`, `enable`, `disable`.** Their real work already lives in
deterministic code (`fuzz.py`, `prob.py`, `commands/*.py`) covered by tiers 1
and 4. The prompt is a dispatcher; its failure modes (calls the wrong tool,
formats the report badly) are low blast radius and immediately visible.

**Does not earn it — `help`, `elaborate`.** Rubric oracles on the parts that
would need testing. `elaborate`'s Z blocks are already covered by its own
`fuzz -t` step.

**Does not earn it — `setup`, `cleanup`.** They mutate the user's machine. An
SDK test of them is expensive and destructive; test the CLI verbs they should
become instead (§5.2 Tier B).

**Scoping conclusion: tier 6 exists for one command.** A tier that pays for
itself on one command should be built for that command and said so, rather than
built as a framework for twenty-one and left unused. If `prove` follows and
nothing else does, the tier was still worth building — and if the §5.1
pushdowns land, the population of candidates *shrinks*, which is the correct
direction.

## 12. Where `tests/commands/test_prompt_contracts.py` sits

It is not a new tier, and it is not "unit tests of Python." It is a **document
conformance check**: an assertion about an artifact — a `.md` file, static data
— against a contract. Its oracle is exact and its cost is zero.

Under §4's split: the prompt's *execution* is non-deterministic; the prompt
*document* is not. The document is Level 1 data even though the program it
encodes is Level 4. That is precisely why it is free, and it is the operator's
framing applied one level up.

**Placement: tier 1, alongside "the spec corpus is a test."** It runs in
`make check`, in the `unit` CI job, with no marker. `TESTING.md`'s tier 1 row
should be widened from "each module behaves in isolation" to include shipped
data files — the prompts and the corpus — since both are already there in
substance.

The placement rule that follows, and it has teeth:

> **Anything assertable about a prompt as a document belongs in tier 1. Tier 6
> asserts only what requires execution.**

For every proposed tier 6 assertion, ask: can this be decided from the file? If
yes, it is a tier 1 assertion that has been mis-filed into a tier that costs
money and cannot be trusted on one sample. `test_prompt_contracts.py` is the
worked example: "the protocol is stated consistently" is decidable from the
file; "the model emits a conforming implementation of it" is not.

Two things this test should gain, neither of which changes its tier:

1. **A cited authority.** Its assertions (`:107-138`) are one reading of
   `oracle.md:1151-1167`. With `examples/oracle-protocol.tex` (§6.2) they become a
   transcription of a model-checked schema, and the docstring says so.
2. **Growth on every tier 6 failure classified as a prompt defect.** §8.3 step
   3 requires it: when a failure turns out to have been decidable from the
   document, the assertion moves down to tier 1 and never costs money again.
   That is the ratchet that keeps tier 6 from growing without bound.

## 13. As a punt-kit standard

### 13.1 `standards/testing.md` should exist

There is no `punt-kit/standards/testing.md`. Testing guidance lives in
`standards/python.md` (a four-row table restating `PL-TT-1`) and in
`../.claude/rules/python-testing.md` (`PL-TT-1` through `PL-TT-6`).

That rules file is scoped `paths: **/*.py`. **The scoping is itself the
defect**: the guidance never loads when an agent edits `commands/*.md`,
`skills/*.md`, `agents/*.md` or `hooks/`. The one directory where the guidance
is most needed is the one directory it cannot reach. And the problem is not
Python's: vox ships hooks, biff ships slash commands, quarry and lux ship
plugins, and dungeon and cryptd are Level 4 applications outright. Every repo
shipping an agentic surface has this gap; z-spec is only where it surfaced.

So: create `standards/testing.md`, language-agnostic, owning the two axes, the
tier definitions, the flakiness ruling and the oracle-pushdown rule — the same
relationship `oo.md` has to `python.md`.

### 13.2 The rules, stated for lifting

Numbered in punt-kit style so promotion is mechanical. All of these generalise;
§13.4 lists what does not.

- **PL-VT-1 — Classify per surface.** Every client surface gets its own
  built-at and designed-for level. A repository that ships both a package and a
  plugin has surfaces at different levels and no single level of its own.
- **PL-VT-2 — The oracle is a second axis.** Record each surface's artifact
  oracle as Exact, Structural or Rubric. The verification method is chosen by
  the oracle, not by the control level.
- **PL-VT-3 — Assert the artifact, never the account.** A model's report that a
  checker passed is not evidence. The test runs the checker.
- **PL-VT-4 — Push the oracle down before the behaviour.** Before writing any
  probabilistic test for an agentic surface, exhaust the deterministic checks on
  its artifact. An agentic command that produces a checkable artifact and does
  not run its checker is a defect, not a design.
- **PL-VT-5 — Decidable from the file means tier 1.** Anything assertable about
  a prompt, skill, hook or agent definition as a *document* is a free
  deterministic test and belongs in the unit tier. Every repository shipping
  such files has at least one such assertion available and most have none
  written.
- **PL-VT-6 — A probabilistic gate never blocks a merge.** It gates the
  release, alarms on drift, and rides in the PR body as pre-PR evidence for
  changed prompts. `PL-TT-4` (flaky tests are bugs) survives intact because the
  probabilistic tier is not in the gate.
- **PL-VT-7 — Zero failures in *n*, and *n* is derived.** Rule of three: `n`
  = 10 for pre-PR evidence, 30 for drift, 60 for release (≈5% upper bound,
  95% confidence). One failure escalates to the release profile before anything
  is concluded; it is never retried into green.
- **PL-VT-8 — Pin two axes.** The release run pins the model version and
  records it; the drift run floats to the model users are served. A suite with
  only the pinned run has stopped testing what ships.
- **PL-VT-9 — Judges last.** Use an LLM judge only when no deterministic
  checker can decide the property, and prefer changing what the surface emits
  so that a checker can.
- **PL-VT-10 — Every result carries three parameters.** Prompt version, fixture,
  model version. A conformance number without all three is not a result.

### 13.3 Concrete edits elsewhere

1. **`../.claude/rules/python-testing.md`, `PL-TT-1`.** Rename tier 4 from
   "SDK — end-to-end with Claude (costs money)" to "Elicitation conformance",
   name its claim, change "Runs in CI: No" to "Not a merge gate; gates the
   release", and cite `standards/testing.md` for the sample policy.
2. **A new rule file**, `../.claude/rules/prompt-testing.md`, with `paths:`
   covering `commands/**/*.md`, `skills/**/*.md`, `agents/**/*.md` and
   `hooks/**`, carrying PL-VT-3, PL-VT-4 and PL-VT-5. This is the
   mechanically important one: it is what makes an agent editing a prompt see
   the discipline at all.
3. **`standards/python.md`.** Its Testing section restates the four-tier table.
   Replace with a cross-reference to `standards/testing.md`, matching how it
   already defers to `architecture.md` and `oo.md`.
4. **`standards/plugins.md`.** Has no testing section — `grep -c test` finds a
   single incidental line. Add one pointing at PL-VT-5, since a plugin repo's
   prompts are its largest untested surface by default.

### 13.4 Out of scope for the standard

`/z-spec:oracle` being the single command that earns the tier here, the Lean
toolchain cost, and the specific fixture design are z-spec facts, not rules.

The one apparent exception is §6.2 — "write the contract as a Z spec and let
the toolchain check it." That reads as a z-spec-specific move, but it is not:
it is the product thesis, and it applies to any punt-labs repo that has z-spec
enabled and ships an agentic surface with a wire contract. Stated as a rule it
would be PL-VT-11, and I am not proposing it yet, because it is untested. §6.2
is the test. If `examples/oracle-protocol.tex` demonstrably prevents the next
protocol divergence, it earns rule status; until then it is a recommendation
with one worked example.

## 14. What I do not know, and what would settle it

Listed in descending order of how much a wrong guess would cost the
implementation mission.

1. **Can the Agent SDK invoke a `commands/*.md` slash command as such?** A
   command file is resolved by Claude Code's plugin loader, with its frontmatter
   `allowed-tools` honoured. If the SDK exposes the same resolution, tier 6
   tests the artifact users run. If it does not, the harness must inline the
   prompt body — which tests the text but not the loading, the frontmatter, or
   the `-dev`/prod swap, and is a materially weaker claim that should be stated
   as such in the tier definition. **Evidence:** read the `claude-agent-sdk`
   documentation and run one spike. **This is the highest-risk unknown and it
   should be resolved before any other tier 6 work.**
2. **What does one run actually cost?** §7 gives arithmetic, not a measurement.
   **Evidence:** one instrumented run of `/z-spec:oracle` against the fixture,
   recording input, output and cache-read tokens and wall clock. Until this
   number exists, *n* = 60 is a statistical argument with no budget attached.
3. **What is the actual conformance rate?** If `oracle` passes 60/60 on the
   first release run, the tier is cheap insurance. If it passes 40/60, the tier
   is telling us the prompt is not ready and the entire cost model changes —
   the right response would be prompt work, not a suite. **Evidence:** the first
   release-profile run. Do not set the published bar before seeing it.
4. **Is Lean's build reproducible enough to be a stable checker?** `lake build`
   with Mathlib is slow and version-sensitive; `prove.md:595-599` already wraps
   it in `timeout 120`. A checker that times out non-deterministically injects
   flakiness on the *deterministic* side of the boundary, which would be the
   worst outcome. **Evidence:** ten consecutive builds of a fixed generated
   project, timed, in the CI image.
5. **Can tier 1 assertions be generated from a Z spec?** §6.2 wants
   `test_prompt_contracts.py` derived from `examples/oracle-protocol.tex` rather
   than transcribed. `parse_spec` (`parser.py:192`) yields predicates as raw
   LaTeX (`types/spec.py:26`), so today it cannot. **Evidence:** a spike parsing
   the `\where` bodies of the 8 specs in `examples/` into a predicate AST,
   reporting the fraction handled. The same spike answers `z-spec-l05` and
   `z-spec-oj3` (§5.2 Tier B), so it is worth doing once for three purposes.
6. **Does the Messages API expose a seed?** §9 asserts not. Verify before
   implementing; if one exists the ruling on `temperature` is unchanged but the
   reproducibility discussion in §9 needs revisiting.

And three documentation defects found while grounding this, which are outside
my write set and are recorded so they are not lost:

- `TESTING.md` states `.github/workflows/` contains only `docs.yml`,
  `release.yml` and `biff-notify.yml`, and that "nothing but markdownlint runs
  in CI." The tree now also has `lint.yml` and `test.yml`, the latter with
  `unit`, `e2e` and `specs` jobs.
- `TESTING.md` states there is no subprocess/E2E tier and that nothing drives
  the installed binary. `tests/e2e/test_installed_cli.py` and
  `tests/e2e/test_installed_mcp.py` do exactly that, and `make test-e2e`
  (`Makefile:40-41`) runs them.
- `TESTING.md` states "z-spec has no markers configured at all."
  `pyproject.toml:127-129` declares `e2e`.

## 15. Implementation order

Each step is a separate mission and each is useful if the next never happens.

1. **§5.2 Tier A, prompt-only.** Widen `allowed-tools` on `model2code.md` and
   `contracts.md` and add mandatory build steps; give `code2model.md` and
   `elaborate.md` explicit pass conditions. Regenerate the `-dev` twins
   (`make gen-dev-commands`). No new infrastructure; buys an Exact oracle on
   1,288 lines of prompt for every user, not only for a test.
2. **§6.2, the Z specification of the oracle protocol.** Joins tiers 2 and 3
   automatically via the `SPECS` wildcard. Re-point
   `test_prompt_contracts.py`'s docstrings at it.
3. **§10's fixture.** The smallest oracle-exercising spec, added to `examples/`
   — free coverage at tiers 2 and 3, and the first row for `/z-spec:oracle` in
   `docs/testing/manual-tests.md`, which today has none.
4. **§14 items 1, 2 and 4 — the spikes.** SDK invocation, one run's cost, Lean
   build stability. Nothing beyond this point should be built before these
   three answers exist.
5. **Tier 6 for `oracle` only.** `sdk` marker, separate workflow, release and
   schedule profiles, results recorded with all three parameters (PL-VT-10).
6. **Promotion to punt-kit** (§13), after the first release-profile run has
   produced a real number to write into the standard.
