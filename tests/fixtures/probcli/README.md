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

## Three facts these transcripts pin down

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
