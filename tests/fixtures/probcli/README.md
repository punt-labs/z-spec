# Captured probcli transcripts

Verbatim output of real `probcli` runs, kept byte-for-byte — ANSI escapes,
absolute paths, and all. `TESTING.md` is explicit about why: a parser test
whose fixture was written from memory passes while the parser is broken.
Nothing in this directory may be hand-edited or hand-written.

Captured with ProB CLI 1.15.1-final (SICStus 4.8.0, arm64-darwin).

## The transcripts

Every model-check row ran with
`-model_check -p DEFAULT_SETSIZE 1 -p MAX_OPERATIONS 200 -p TIME_OUT 300000 -coverage`.

| File | Source | What it holds |
|------|--------|---------------|
| `init.out` | `examples/search-panel.tex -init -p DEFAULT_SETSIZE 1` | the declared `Z operation:` list, no census |
| `animate.out` | `examples/search-panel.tex -animate 20 -p DEFAULT_SETSIZE 1 -coverage` | a census with one uncovered operation |
| `model-check-covered.out` | `examples/search-panel.tex` | `UNCOVERED_OPERATIONS (0)` |
| `model-check-uncovered.out` | `specs/unreachable-operation-bad.tex` | `UNCOVERED_OPERATIONS (1),Freeze` |
| `model-check-xi-uncovered.out` | `specs/xi-frame-bad.tex` | `UNCOVERED_OPERATIONS (1),RejectWithdraw` |
| `model-check-counter-example.out` | `specs/deadlock-bad.tex` | `*** COUNTER EXAMPLE FOUND ***`, a one-step trace, and `UNCOVERED_OPERATIONS (1),Step` |
| `model-check-covered-then-deadlock.out` | `specs/covered-then-deadlock-bad.tex` | `ALL OPERATIONS COVERED` **and** a counter-example, in that order |
| `model-check-incomplete.out` | `examples/claude-code.tex` at `MAX_OPERATIONS=200` | `model_check_incomplete` beside `No counter example found` |
| `model-check-hidden-deadlock.out` | `specs/hidden-deadlock-bad.tex` at `MAX_OPERATIONS=3` | a truncated run reporting no counter-example on a spec that **has** one |
| `cbc-assertions.out` | `examples/search-panel.tex -cbc_assertions` | no census — the run never asked |
| `cbc-deadlock.out` | `examples/search-panel.tex -cbc_deadlock` | no census — the run never asked |

To re-capture one, run its command and redirect stdout and stderr into the
file. Do not edit the result.

## The specs that make a gate go red

`specs/` holds the three specifications behind the failing transcripts. All
three are **fuzz-clean** — that is the point. Each defect passes the
type-check tier untouched and is visible only at the model-check tier, which is
why the `-bad` suffix sits on the file rather than on a type error.

| Spec | Defect | Which gate it reddens |
|------|--------|----------------------|
| `deadlock-bad.tex` | initial state `count = 0` and the only operation requires `count > 0`, so nothing is ever enabled | counter-example |
| `covered-then-deadlock-bad.tex` | `Step` fires to the bound and then nothing is enabled: full coverage, and a deadlock | counter-example, with coverage passing |
| `unreachable-operation-bad.tex` | `Freeze` requires `balance > maxBalance`, which the state invariant forbids | coverage |
| `xi-frame-bad.tex` | `RejectWithdraw`'s `\Xi` frame is broken, so the operation is unsatisfiable | coverage |
| `hidden-deadlock-bad.tex` | one deadlock among 1000 **distinct** successors of a single operation | model-check, but only when not truncated |

They live here rather than in `examples/`, which is the specimen corpus —
documentation of how to write Z well. These are reproduction artifacts for the
parser. The `SPECS` wildcard globs `examples/*.tex`, so nothing here joins the
gate wherever it sits.

## Why a hand-written fixture is the same defect as an inferred answer

A parser that infers what a tool would have said, and a test that asserts
against a string the tool does not emit, are one mistake wearing two hats.
Both substitute a plausible answer for a measured one, and both agree with a
broken implementation.

The concrete case: `probcli --version` prints `ProB Command Line Interface` and
then `VERSION 1.15.1-final`, and no run in this repository passes `--version`,
so `probcli_version` is `"unknown"` — truthful, because nothing was asked. The
test suite nonetheless asserted `probcli_version == "1.13.1"`, which passed
against an invented `ProB CLI Version 1.13.1` fixture and would have passed
against any parser at all. It attested to a fact about a tool nobody had asked
the tool for.

That is why nothing in this directory may be written by hand. A fixture is a
record of what a program printed, or it is a guess with a test wrapped round
it.

## Which claims survive a truncated run, and which do not

`model-check-incomplete.out` is one run reporting two kinds of claim side by
side, in one bracket, with identical apparent confidence. They are not equally
trustworthy, and the difference is the whole reason that transcript is kept.

**Existential claims survive truncation.** "This operation fired at least once"
and "a counter-example exists" are both witnessed by something the run saw.
More exploration only ever adds witnesses, so a truncated run can *under*-report
them but never over-report. `UNCOVERED_OPERATIONS (0)` from an incomplete run is
therefore sound, and arguably stronger: every operation fired despite the run
being cut short.

**Universal claims do not.** "No counter-example found", `deadlocked:0`, and
`invariant_violated:0` are claims about *all* reachable states. A run that
stopped short cannot establish any of them, however clean the output reads.

That a truncated run **can** hide a real violation is not deduced, it is
demonstrated. `specs/hidden-deadlock-bad.tex` has a genuine deadlock, and at
`MAX_OPERATIONS=2000` probcli finds it. `model-check-hidden-deadlock.out` is
the same specification at `MAX_OPERATIONS=3`:

```text
ALL OPERATIONS COVERED
% Model checking finished, all open states visited
States analysed: 4
No counter example found. However, not all transitions were computed !
[STATES (5),deadlocked:0,...,UNCOVERED_OPERATIONS (0)]
probcli exit: 0
```

Every signal a clean run gives — `deadlocked:0`, full coverage, all open states
visited, exit 0 — on a specification that deadlocks. Only the incompleteness
marker separates the two runs.

Getting there took three attempts, and the failures are the useful part.
`MAX_OPERATIONS` bounds the transitions computed **per operation**, and
transitions that share a successor collapse. So a trap reachable through a
second operation is always found, and a trap behind a *shared* successor is
always found however hard the run is truncated. Only a trap behind its own
distinct successor, among more distinct successors than the bound allows, is
lost — cut that transition and the state is never visited, never checked, never
reported. That is the shape to reach for when testing this class of failure.

Two consequences, both encoded in `ProbOutput`:

- An incomplete run's model-check verdict is `warning`, not `passed`, and
  `ProbReport.ok` does not count `warning` as passing. Reporting an
  unestablished universal claim as success is the failure this whole directory
  exists to document.
- Its coverage verdict is untouched: the census is read and trusted, because
  coverage is the existential half.

The mirror case is worth naming too. `UNCOVERED_OPERATIONS (n>0)` from a
truncated run is *not* proof of dead specification — "did not fire in the part
explored" is not "cannot fire". Under-reporting coverage is over-reporting
uncovered.

## Four facts these transcripts pin down

**probcli exits 0 when it finds a counter-example.**
`model-check-counter-example.out` came from a run whose exit status was `0`,
printed alongside `*** COUNTER EXAMPLE FOUND ***` in red. So the model-check
gate that read that exit code was not merely loose — it could never fail, and
the recipe replacing it was given the ability to fail at all. That the old grep
pattern set happens to contain `COUNTER` changes nothing: grep's status was
discarded, and probcli's was the target's verdict.

**An unreachable operation changes nothing else in the output.**
`model-check-uncovered.out` is byte-identical to a clean run on every line the
old grep printed — the same `States analysed`, the same `Transitions fired`,
the same `No counter example found. ALL states visited.` There is no anomaly to
spot. That is why this went unseen: not because nobody looked, but because
looking could not have helped. Only asking the question and reading the answer
does.

**probcli announces success as it goes, and finds the failure afterwards.**
`model-check-covered-then-deadlock.out` prints `ALL OPERATIONS COVERED` and
then, four lines later, `*** COUNTER EXAMPLE FOUND ***`. Both are true: every
operation fires, and the run still failed. So a marker's presence never settles
a run — it settles the one question that marker answers. The counter-example
must be tested first and unconditionally, and coverage must be a separate
verdict rather than an input to this one.

**A branch that cannot execute is worse than a branch that is missing.**
`_exit_verdict` used to carry a `"not all transitions" -> warning` case. It
could never run: probcli prints that phrase beside `No counter example found`,
and the branch testing for *that* returned first. So the file documented a case
it did not handle, and every reader who audited it — four of us — saw
incompleteness covered and moved on. A missing branch is visible; an unreachable
one is camouflage. When adding a defensive case, prove it fires.
