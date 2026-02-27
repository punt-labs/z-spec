---
description: Generate property-based test harness using Lean 4 model as oracle
argument-hint: "[spec.tex] [language: swift|typescript|python|kotlin] [--sequences N] [--steps N]"
allowed-tools: Bash(which:*), Bash(lean:*), Bash(lake:*), Read, Glob, Grep, Write
---

# /z-spec:oracle - Property-Based Oracle Testing

Generate a property-based test harness that uses the executable Lean 4
model (from `/z-spec:prove`) as a test oracle. For random sequences of
operations, the harness executes them against both the Lean model and
the real implementation, applies an abstraction function to map concrete
state to abstract state, and asserts they match.

This is QuickCheck against a proven-correct reference implementation.

## Input

Arguments: $ARGUMENTS

Parse arguments:

- First positional argument: Z specification file (default: search `docs/*.tex`)
- Second positional argument: target language (`swift`, `typescript`, `python`, `kotlin`)
  - If not specified, auto-detect from project files
- `--sequences N` - number of random sequences to test (default: 100)
- `--steps N` - max operations per sequence (default: 20)

## Process

### 0. Prerequisites

Verify Lean 4 and Lake are installed:

```bash
which lean >/dev/null 2>&1 || echo "LEAN_NOT_FOUND"
which lake >/dev/null 2>&1 || echo "LAKE_NOT_FOUND"
```

**If lean or lake not found**: Stop and tell the user:
> Lean 4 is not installed. Run `/z-spec:setup lean` to install
> the Lean 4 toolchain via elan.

Verify the Lean project from `/z-spec:prove` exists:

```bash
ls proofs/lakefile.toml 2>/dev/null && echo "PROJECT_EXISTS"
ls proofs/ZSpec/State.lean 2>/dev/null && echo "STATE_EXISTS"
ls proofs/ZSpec/Operations.lean 2>/dev/null && echo "OPS_EXISTS"
```

**If proofs/ does not exist or is incomplete**: Stop and tell the user:
> The Lean 4 project is missing or incomplete. Run `/z-spec:prove`
> first to generate the Lean model, then run `/z-spec:oracle`.

Verify Lean version compatibility:

```bash
lean --version 2>&1
```

The output should show Lean 4.x. If it shows Lean 3.x or an error,
advise the user to update via `elan update`.

The Z specification should already exist and have been type-checked
(via `/z-spec:check`). If the user has not done this, suggest it
but do not block.

### 1. Locate the Specification

If a file path is provided, use it directly.

If no file specified:

- Look in `docs/` for `.tex` files containing Z specifications
- If multiple found, ask user to specify

Read the specification file.

### 2. Parse the Specification

Scan the specification and extract the following constructs.
Each subsection describes what to look for and what to record.

#### 2a. Given Sets

Look for given set declarations in `\begin{zed}` blocks:

```latex
\begin{zed}
[USERID, SESSIONID]
\end{zed}
```

Record each name. These become symbolic value pools in the test
harness generators.

#### 2b. Free Types

Look for free type definitions in `\begin{zed}` blocks:

```latex
\begin{zed}
Status ::= pending | active | suspended | closed
\end{zed}
```

Record the type name and all constructors. These become `oneOf`
generators in the property-based test.

#### 2c. Axiomatic Definitions

Look for `\begin{axdef}` blocks with global constants:

```latex
\begin{axdef}
MAX\_BALANCE : \nat
\where
MAX\_BALANCE = 1000000
\end{axdef}
```

Record each constant name, type, and defining predicate. These
constrain the generators.

#### 2d. State Schemas

Look for state schemas -- schemas that are **not** operations
(no `\Delta`, `\Xi`, or primed-only variables) and contain
a `\where` block with invariant predicates:

```latex
\begin{schema}{Account}
balance : \num \\
status : Status
\where
balance \geq 0 \lor status = suspended \\
status = closed \implies balance = 0
\end{schema}
```

Record:

- **Name**: The schema name
- **Fields**: Each variable name and its Z type
- **Invariants**: All predicates in the `\where` block

#### 2e. Init Schemas

Look for schemas that initialize the state:

```latex
\begin{schema}{InitAccount}
Account'
\where
balance' = 0 \\
status' = pending
\end{schema}
```

Record:

- **Name**: The schema name
- **Target state**: The referenced state schema
- **Initial values**: Assignments to primed variables

#### 2f. Operation Schemas

Look for schemas containing `\Delta` or `\Xi`:

```latex
\begin{schema}{Deposit}
\Delta Account \\
amount? : \nat_1
\where
status = active \\
balance' = balance + amount? \\
status' = status
\end{schema}
```

For each operation, record:

- **Name**: The schema name
- **Kind**: `\Delta` (state-changing) or `\Xi` (query/observation)
- **State schema**: The referenced state schema name
- **Inputs**: Variables ending in `?` with their types
- **Outputs**: Variables ending in `!` with their types
- **Preconditions**: Predicates referencing only unprimed state
  variables and/or inputs
- **Effects**: Predicates referencing primed variables (`x'`)
- **Frame conditions**: Predicates of the form `x' = x`

### 3. Verify Lean Model Consistency

Before generating the oracle, verify that the Lean model in
`proofs/ZSpec/` matches the specification:

#### 3a. Check Structure Fields

Read `proofs/ZSpec/State.lean` and verify that every field in the
Z state schema has a corresponding field in the Lean `structure`.
If fields are missing or mismatched, warn:

> Warning: Lean model may be out of sync with specification.
> State field `{field}` in spec but not in Lean model.
> Consider re-running `/z-spec:prove` to regenerate.

#### 3b. Check Operations

Read `proofs/ZSpec/Operations.lean` and verify that every Delta
and Xi operation in the Z spec has a corresponding Lean function.
If operations are missing, warn:

> Warning: Operation `{name}` is in the spec but not in the
> Lean model. The oracle will skip this operation.

#### 3c. Check Init

Verify that an init function exists in `Operations.lean`.
The oracle needs this to initialize Lean state.

### 4. Detect Target Language

If language specified as an argument, use it.

Otherwise auto-detect from project files:

| File Present | Language |
|--------------|----------|
| `Package.swift`, `*.xcodeproj` | Swift |
| `package.json`, `tsconfig.json` | TypeScript |
| `pyproject.toml`, `setup.py`, `requirements.txt` | Python |
| `build.gradle.kts`, `pom.xml` | Kotlin |

If no language detected, ask the user to specify.

### 5. Generate Lean Executable Oracle

Generate a `proofs/ZSpec/Oracle.lean` file that provides a
command-line executable for running operations on the Lean model.
The oracle reads JSON commands from stdin and writes JSON state
to stdout.

#### 5a. Oracle Module

```lean
/-
  ZSpec.Oracle
  Generated from: <spec-file-name>
  Date: <current-date>

  Executable oracle for property-based testing.
  Reads JSON operation commands from stdin, executes them
  on the Lean model, and outputs resulting state as JSON.
-/

import ZSpec.State
import ZSpec.Operations

-- JSON serialization for state
def stateToJson (s : <StateName>) : String :=
  "{" ++
  -- One entry per field:
  "\"<field1>\": " ++ toString s.<field1> ++ ", " ++
  "\"<field2>\": " ++ "\"" ++ toString s.<field2> ++ "\"" ++
  "}"

-- JSON serialization for free types
def <FreeType>.toJsonString : <FreeType> -> String
  | .<constructor1> => "\"<constructor1>\""
  | .<constructor2> => "\"<constructor2>\""
  -- one case per constructor

-- Parse a single operation from a JSON-like line
-- Format: {"op": "<name>", "args": {<key>: <value>, ...}}
def parseAndExecute (s : <StateName>) (line : String) :
    <StateName> := do
  -- Extract operation name
  -- Match on operation name and dispatch
  -- Return updated state (or same state for Xi operations)
  -- If precondition fails, return state unchanged
  s  -- fallback: no change

/-- Main entry point: read commands line by line, execute each,
    output resulting state as JSON after each step. -/
def main : IO Unit := do
  let stdin <- IO.getStdin
  let stdout <- IO.getStdout
  -- Read initial state
  let mut state := <initFunction>
  -- Output initial state
  stdout.putStrLn (stateToJson state)
  -- Process commands until EOF
  let mut line <- stdin.getLine
  while !line.isEmpty do
    let trimmed := line.trim
    if !trimmed.isEmpty then
      state := parseAndExecute state trimmed
      stdout.putStrLn (stateToJson state)
    line <- stdin.getLine
```

**Translation rules for the oracle module**:

- Each state field needs a `toString` representation in `stateToJson`
- `Nat` and `Int` use `toString` directly
- Free types need a custom `toJsonString` function
- Given sets need a string representation (use `sorry` with a
  comment that the user must provide a `ToString` instance)
- Partial functions (`X -> Option Y`) serialize as JSON objects
- Sets (`Finset X`) serialize as JSON arrays
- Sequences (`List X`) serialize as JSON arrays

**Parsing rules**:

- Use simple string matching for the JSON-like input format
- The test harness controls the exact format, so it can be simple
- Each operation dispatches to the corresponding Lean function
- If a precondition cannot be checked at runtime (it is a `Prop`,
  not a `Bool`), add a `Decidable` instance or a boolean version:

```lean
def deposit_precondition_bool (s : Account) (amount : Nat) : Bool :=
  s.status == Status.active && amount > 0
```

#### 5b. Update lakefile.toml

Add an executable target to `proofs/lakefile.toml`:

```toml
[[lean_exe]]
name = "oracle"
root = "ZSpec.Oracle"
```

**Check first** whether the `[[lean_exe]]` section for `oracle`
already exists. If it does, do not duplicate it.

#### 5c. Build the Oracle

```bash
cd proofs && lake build oracle 2>&1
```

If the build fails, report the errors and suggest fixes.
Common issues:

- Missing `ToString` instances for opaque types
- `Decidable` instances needed for `if` conditions on `Prop`
- Import errors from missing modules

If the build succeeds, report:

> Lean oracle built successfully: `proofs/.lake/build/bin/oracle`

### 6. Generate Abstraction Function

Generate a function in the target language that maps concrete
application state to the abstract state matching the Lean model.
This is the **key bridging artifact** -- the user must verify and
customize it.

#### 6a. TypeScript

```typescript
// oracle/abstraction.ts
// Generated abstraction function -- USER MUST CUSTOMIZE
//
// Maps concrete application state to the abstract state
// that matches the Lean model. Every field must correspond
// to a field in the Lean State structure.

interface AbstractState {
  // One field per state schema variable
  <field1>: <tsType1>;
  <field2>: <tsType2>;
  // ...
}

/**
 * Map concrete application state to abstract state.
 *
 * This function is the refinement relation: it defines how
 * the implementation's data structures correspond to the
 * specification's mathematical model.
 *
 * @param concrete - The real application state
 * @returns The abstract state matching the Lean model
 */
function abstractState(concrete: ConcreteState): AbstractState {
  return {
    <field1>: concrete.<field1>,      // TODO: verify mapping
    <field2>: map<Field2>(concrete.<field2>), // TODO: customize
    // ...
  };
}

// Helper: map concrete enum to abstract enum string
function mapStatus(status: ConcreteStatus): string {
  // TODO: Map your concrete status type to the Z free type values
  switch (status) {
    case ConcreteStatus.Active: return "active";
    case ConcreteStatus.Pending: return "pending";
    // ...
  }
}

export { AbstractState, abstractState };
```

#### 6b. Python

```python
# oracle/abstraction.py
# Generated abstraction function -- USER MUST CUSTOMIZE

from dataclasses import dataclass
from typing import Any


@dataclass
class AbstractState:
    """Abstract state matching the Lean model."""
    # One field per state schema variable
    # <field1>: <pyType1>
    # <field2>: <pyType2>
    pass


def abstract_state(concrete: Any) -> AbstractState:
    """Map concrete application state to abstract state.

    This function is the refinement relation: it defines how
    the implementation's data structures correspond to the
    specification's mathematical model.

    Args:
        concrete: The real application state

    Returns:
        The abstract state matching the Lean model
    """
    return AbstractState(
        # <field1>=concrete.<field1>,      # TODO: verify mapping
        # <field2>=map_status(concrete.<field2>),  # TODO: customize
    )


def map_status(status: Any) -> str:
    """Map concrete enum to abstract free type value.

    TODO: Map your concrete status type to the Z free type values.
    """
    mapping = {
        # ConcreteStatus.ACTIVE: "active",
        # ConcreteStatus.PENDING: "pending",
    }
    return mapping[status]
```

#### 6c. Swift

```swift
// oracle/Abstraction.swift
// Generated abstraction function -- USER MUST CUSTOMIZE

/// Abstract state matching the Lean model.
struct AbstractState: Equatable, Codable {
    // One field per state schema variable
    // let <field1>: <swiftType1>
    // let <field2>: <swiftType2>
}

/// Map concrete application state to abstract state.
///
/// This function is the refinement relation: it defines how
/// the implementation's data structures correspond to the
/// specification's mathematical model.
func abstractState(_ concrete: ConcreteState) -> AbstractState {
    AbstractState(
        // <field1>: concrete.<field1>,      // TODO: verify mapping
        // <field2>: mapStatus(concrete.<field2>)  // TODO: customize
    )
}

/// Map concrete enum to abstract free type value.
func mapStatus(_ status: ConcreteStatus) -> String {
    // TODO: Map your concrete status type to the Z free type values
    switch status {
    case .active: return "active"
    case .pending: return "pending"
    // ...
    }
}
```

#### 6d. Kotlin

```kotlin
// oracle/Abstraction.kt
// Generated abstraction function -- USER MUST CUSTOMIZE

/**
 * Abstract state matching the Lean model.
 */
data class AbstractState(
    // One field per state schema variable
    // val <field1>: <kotlinType1>,
    // val <field2>: <kotlinType2>,
)

/**
 * Map concrete application state to abstract state.
 *
 * This function is the refinement relation: it defines how
 * the implementation's data structures correspond to the
 * specification's mathematical model.
 */
fun abstractState(concrete: ConcreteState): AbstractState {
    return AbstractState(
        // <field1> = concrete.<field1>,      // TODO: verify mapping
        // <field2> = mapStatus(concrete.<field2>),  // TODO: customize
    )
}

/**
 * Map concrete enum to abstract free type value.
 */
fun mapStatus(status: ConcreteStatus): String {
    // TODO: Map your concrete status type to the Z free type values
    return when (status) {
        ConcreteStatus.ACTIVE -> "active"
        ConcreteStatus.PENDING -> "pending"
        // ...
        else -> throw IllegalArgumentException("Unknown status: $status")
    }
}
```

#### 6e. Marking TODOs

For every field in the abstraction function:

- If the field name and type match directly between concrete and
  abstract (same name, compatible type), emit the mapping without
  a TODO comment
- If the field name differs, emit a mapping with:
  `// TODO: verify -- concrete.<concreteName> maps to abstract <abstractName>`
- If the type differs (e.g., concrete enum vs. abstract string),
  emit a helper function call with:
  `// TODO: customize enum mapping`
- If the field has no obvious concrete counterpart, emit:
  `// TODO: no obvious mapping -- provide concrete source`

### 7. Generate Operation Generators

For each operation, generate a random input generator that
respects the operation's input types and basic constraints.

#### 7a. Generator Type Mappings

| Z Type | TypeScript (fast-check) | Python (hypothesis) | Swift | Kotlin (kotest) |
|--------|------------------------|--------------------|--------------------|-----------------|
| `\nat` | `fc.nat()` | `st.integers(min_value=0)` | `Int.random(in: 0...1000)` | `Arb.int(0..1000)` |
| `\nat_1` | `fc.nat({min: 1})` | `st.integers(min_value=1)` | `Int.random(in: 1...1000)` | `Arb.int(1..1000)` |
| `\num` | `fc.integer()` | `st.integers()` | `Int.random(in: -1000...1000)` | `Arb.int(-1000..1000)` |
| Free type | `fc.constantFrom(...)` | `st.sampled_from(...)` | `.random()` on cases | `Arb.of(...)` |
| Given set `[X]` | `fc.constantFrom("x1","x2","x3")` | `st.sampled_from(["x1","x2","x3"])` | `["x1","x2","x3"].randomElement()!` | `Arb.of("x1","x2","x3")` |
| `\power X` | `fc.uniqueArray(genX)` | `st.frozensets(genX)` | `Set(Array(...).shuffled().prefix(n))` | `Arb.set(genX)` |
| `\seq X` | `fc.array(genX)` | `st.lists(genX)` | `(0..<n).map { _ in genX() }` | `Arb.list(genX)` |
| `a \upto b` | `fc.integer({min:a, max:b})` | `st.integers(min_value=a, max_value=b)` | `Int.random(in: a...b)` | `Arb.int(a..b)` |

#### 7b. Bounded Value Generators

When the spec constrains an input (e.g., `amount? \leq balance`),
the generator should respect the constraint to produce valid
inputs. Use `filter` or conditional generation:

```typescript
// amount? <= balance: generate amount relative to current state
const amountArb = (balance: number) =>
  fc.integer({ min: 1, max: Math.max(1, balance) });
```

For state-dependent constraints, the generator takes the current
state as a parameter and produces valid inputs for that state.

#### 7c. Operation Arbitrary

Combine all operation generators into a single arbitrary that
picks a random operation:

**TypeScript (fast-check)**:

```typescript
// One record type per operation
type Operation =
  | { op: 'deposit'; amount: number }
  | { op: 'withdraw'; amount: number }
  | { op: 'getBalance' }
  // ... one variant per operation

// Generator for a single operation (state-independent inputs)
const operationArb: fc.Arbitrary<Operation> = fc.oneof(
  fc.record({
    op: fc.constant('deposit' as const),
    amount: fc.integer({ min: 1, max: 10000 }),
  }),
  fc.record({
    op: fc.constant('withdraw' as const),
    amount: fc.integer({ min: 1, max: 10000 }),
  }),
  fc.record({
    op: fc.constant('getBalance' as const),
  }),
  // ... one per operation
);
```

**Python (hypothesis)**:

```python
from hypothesis import strategies as st

# One strategy per operation
def operation_strategy():
    return st.one_of(
        st.fixed_dictionaries({
            "op": st.just("deposit"),
            "amount": st.integers(min_value=1, max_value=10000),
        }),
        st.fixed_dictionaries({
            "op": st.just("withdraw"),
            "amount": st.integers(min_value=1, max_value=10000),
        }),
        st.fixed_dictionaries({
            "op": st.just("get_balance"),
        }),
        # ... one per operation
    )
```

**Swift**:

```swift
// Operation enum with associated values
enum Operation {
    case deposit(amount: Int)
    case withdraw(amount: Int)
    case getBalance

    static func random() -> Operation {
        switch Int.random(in: 0..<3) {
        case 0: return .deposit(amount: Int.random(in: 1...10000))
        case 1: return .withdraw(amount: Int.random(in: 1...10000))
        default: return .getBalance
        }
    }
}
```

**Kotlin (kotest)**:

```kotlin
sealed class Operation {
    data class Deposit(val amount: Int) : Operation()
    data class Withdraw(val amount: Int) : Operation()
    data object GetBalance : Operation()
}

fun arbOperation(): Arb<Operation> = Arb.choice(
    Arb.int(1..10000).map { Operation.Deposit(it) },
    Arb.int(1..10000).map { Operation.Withdraw(it) },
    Arb.constant(Operation.GetBalance),
)
```

### 8. Generate Property-Based Test Driver

Generate a test file that:

1. Initializes both the Lean oracle and the concrete system
2. Generates random sequences of valid operations
3. Executes each operation on both sides
4. Applies the abstraction function to concrete state
5. Asserts abstract states match after every step

#### 8a. TypeScript (fast-check / Jest)

```typescript
// oracle/oracle.test.ts
import fc from 'fast-check';
import { execSync, spawn } from 'child_process';
import { AbstractState, abstractState } from './abstraction';

// Path to the Lean oracle binary
const ORACLE_BIN = 'proofs/.lake/build/bin/oracle';

// Number of sequences and max steps from arguments
const NUM_SEQUENCES = <sequences>;
const MAX_STEPS = <steps>;

/**
 * Send a command to the Lean oracle process and read the
 * resulting state as JSON.
 */
function sendToOracle(
  proc: ReturnType<typeof spawn>,
  command: Operation,
): Promise<AbstractState> {
  return new Promise((resolve, reject) => {
    const json = JSON.stringify(command);
    proc.stdin!.write(json + '\n');

    proc.stdout!.once('data', (data: Buffer) => {
      try {
        const state = JSON.parse(data.toString().trim());
        resolve(state as AbstractState);
      } catch (e) {
        reject(new Error(`Failed to parse oracle output: ${data}`));
      }
    });
  });
}

/**
 * Execute an operation on the concrete system.
 * TODO: Import your concrete system and implement dispatch.
 */
function executeConcreteOp(
  state: ConcreteState,
  op: Operation,
): void {
  switch (op.op) {
    case 'deposit':
      // TODO: state.deposit(op.amount);
      break;
    case 'withdraw':
      // TODO: state.withdraw(op.amount);
      break;
    case 'getBalance':
      // TODO: state.getBalance();
      break;
    // ... one case per operation
  }
}

describe('Oracle: concrete refines abstract model', () => {
  it('matches Lean model for random operation sequences', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(operationArb, {
          minLength: 1,
          maxLength: MAX_STEPS,
        }),
        async (operations) => {
          // Start fresh oracle process
          const oracle = spawn(ORACLE_BIN);

          // Read initial state from oracle
          const initLine = await new Promise<string>((resolve) => {
            oracle.stdout!.once('data', (data: Buffer) => {
              resolve(data.toString().trim());
            });
          });
          let leanState: AbstractState = JSON.parse(initLine);

          // Initialize concrete system
          // TODO: const concreteState = new ConcreteState();
          const concreteState: any = {}; // placeholder

          // Execute each operation on both sides
          for (const op of operations) {
            leanState = await sendToOracle(oracle, op);
            executeConcreteOp(concreteState, op);

            const abstracted = abstractState(concreteState);
            expect(abstracted).toEqual(leanState);
          }

          oracle.kill();
        },
      ),
      { numRuns: NUM_SEQUENCES },
    );
  });
});
```

#### 8b. Python (hypothesis / pytest)

```python
# oracle/test_oracle.py
import json
import subprocess
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from oracle.abstraction import abstract_state, AbstractState

ORACLE_BIN = "proofs/.lake/build/bin/oracle"
NUM_SEQUENCES = <sequences>
MAX_STEPS = <steps>


class OracleProcess:
    """Manages the Lean oracle subprocess."""

    def __init__(self):
        self.proc = subprocess.Popen(
            [ORACLE_BIN],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        # Read initial state
        line = self.proc.stdout.readline().strip()
        self.state = json.loads(line)

    def execute(self, op: dict) -> dict:
        """Send operation to oracle, return new state."""
        self.proc.stdin.write(json.dumps(op) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline().strip()
        self.state = json.loads(line)
        return self.state

    def close(self):
        self.proc.terminate()
        self.proc.wait()


def execute_concrete_op(state, op: dict):
    """Execute operation on the concrete system.

    TODO: Import your concrete system and implement dispatch.
    """
    op_name = op["op"]
    # if op_name == "deposit":
    #     state.deposit(op["amount"])
    # elif op_name == "withdraw":
    #     state.withdraw(op["amount"])
    # ...


class TestOracle:
    """Property-based tests: concrete system refines abstract model."""

    @given(
        operations=st.lists(
            operation_strategy(),
            min_size=1,
            max_size=MAX_STEPS,
        )
    )
    @settings(
        max_examples=NUM_SEQUENCES,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_concrete_refines_abstract(self, operations):
        """For any sequence of operations, concrete state
        (abstracted) must match Lean model state."""
        oracle = OracleProcess()

        try:
            # TODO: Initialize concrete system
            concrete_state = None  # placeholder

            for op in operations:
                lean_state = oracle.execute(op)
                execute_concrete_op(concrete_state, op)

                abstracted = abstract_state(concrete_state)
                assert abstracted.__dict__ == lean_state, (
                    f"State mismatch after {op}: "
                    f"concrete={abstracted}, lean={lean_state}"
                )
        finally:
            oracle.close()
```

#### 8c. Swift (swift-testing)

```swift
// oracle/OracleTests.swift
import Testing
import Foundation

let oracleBin = "proofs/.lake/build/bin/oracle"
let numSequences = <sequences>
let maxSteps = <steps>

/// Manages the Lean oracle subprocess.
class OracleProcess {
    let process: Process
    let stdin: Pipe
    let stdout: Pipe

    init() throws {
        process = Process()
        process.executableURL = URL(fileURLWithPath: oracleBin)
        stdin = Pipe()
        stdout = Pipe()
        process.standardInput = stdin
        process.standardOutput = stdout
        try process.run()

        // Read initial state
        _ = readLine()
    }

    func execute(_ op: Operation) -> [String: Any] {
        let json = op.toJSON()
        stdin.fileHandleForWriting.write(
            (json + "\n").data(using: .utf8)!
        )
        let line = readLine()
        return parseJSON(line)
    }

    private func readLine() -> String {
        // Read until newline from stdout
        var data = Data()
        let handle = stdout.fileHandleForReading
        while true {
            let byte = handle.readData(ofLength: 1)
            if byte.isEmpty || byte[0] == 0x0A { break }
            data.append(byte)
        }
        return String(data: data, encoding: .utf8) ?? ""
    }

    private func parseJSON(_ s: String) -> [String: Any] {
        guard let data = s.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(
                  with: data
              ) as? [String: Any]
        else { return [:] }
        return obj
    }

    func close() {
        process.terminate()
    }
}

/// Execute operation on concrete system.
/// TODO: Import your concrete types and implement dispatch.
func executeConcreteOp(
    _ state: inout ConcreteState,
    _ op: Operation
) {
    switch op {
    case .deposit(let amount):
        break // TODO: state.deposit(amount: amount)
    case .withdraw(let amount):
        break // TODO: state.withdraw(amount: amount)
    case .getBalance:
        break // TODO: _ = state.getBalance()
    }
}

@Suite("Oracle: concrete refines abstract model")
struct OracleTests {
    @Test("matches Lean model for random operation sequences",
          arguments: 0..<numSequences)
    func oracleMatch(seed: Int) throws {
        let oracle = try OracleProcess()
        defer { oracle.close() }

        // TODO: var concreteState = ConcreteState()

        let steps = Int.random(in: 1...maxSteps)
        for _ in 0..<steps {
            let op = Operation.random()
            let leanState = oracle.execute(op)
            // executeConcreteOp(&concreteState, op)
            // let abstracted = abstractState(concreteState)
            // #expect(abstracted == leanState)
        }
    }
}
```

#### 8d. Kotlin (kotest)

```kotlin
// oracle/OracleTest.kt
import io.kotest.core.spec.style.FunSpec
import io.kotest.matchers.shouldBe
import io.kotest.property.Arb
import io.kotest.property.arbitrary.list
import io.kotest.property.checkAll
import com.google.gson.Gson
import java.io.BufferedReader
import java.io.InputStreamReader

const val ORACLE_BIN = "proofs/.lake/build/bin/oracle"
const val NUM_SEQUENCES = <sequences>
const val MAX_STEPS = <steps>

class OracleProcess : AutoCloseable {
    private val process: Process =
        ProcessBuilder(ORACLE_BIN).start()
    private val reader = BufferedReader(
        InputStreamReader(process.inputStream)
    )
    private val writer = process.outputStream.bufferedWriter()
    private val gson = Gson()
    var state: Map<String, Any>

    init {
        // Read initial state
        val line = reader.readLine()
        state = gson.fromJson(line, Map::class.java)
            as Map<String, Any>
    }

    fun execute(op: Operation): Map<String, Any> {
        writer.write(op.toJson() + "\n")
        writer.flush()
        val line = reader.readLine()
        state = gson.fromJson(line, Map::class.java)
            as Map<String, Any>
        return state
    }

    override fun close() {
        process.destroy()
    }
}

/**
 * Execute operation on the concrete system.
 * TODO: Import your concrete types and implement dispatch.
 */
fun executeConcreteOp(state: Any, op: Operation) {
    when (op) {
        is Operation.Deposit -> Unit // TODO
        is Operation.Withdraw -> Unit // TODO
        is Operation.GetBalance -> Unit // TODO
    }
}

class OracleTest : FunSpec({
    test("concrete refines abstract model").config(
        invocations = NUM_SEQUENCES
    ) {
        checkAll(
            Arb.list(arbOperation(), 1..MAX_STEPS)
        ) { operations ->
            OracleProcess().use { oracle ->
                // TODO: val concreteState = ConcreteState()

                for (op in operations) {
                    val leanState = oracle.execute(op)
                    // executeConcreteOp(concreteState, op)
                    // val abstracted = abstractState(concreteState)
                    // abstracted shouldBe leanState
                }
            }
        }
    }
})
```

### 9. Generate JSON Protocol Types

Generate a shared protocol definition that both the Lean oracle
and the test harness use. This ensures the JSON format is consistent.

#### 9a. Protocol Definition

The JSON protocol uses newline-delimited JSON (NDJSON). Each line
is a complete JSON object.

**Command format** (test harness to oracle):

```json
{"op": "<operation-name>", "args": {"<input1>": <value1>, "<input2>": <value2>}}
```

**State format** (oracle to test harness):

```json
{"<field1>": <value1>, "<field2>": "<value2>"}
```

#### 9b. Type Serialization

| Z Type | JSON Representation |
|--------|---------------------|
| `\nat`, `\nat_1` | JSON number |
| `\num` | JSON number |
| Free type constructor | JSON string (constructor name) |
| Given set element | JSON string (symbolic name) |
| `\power X` | JSON array (sorted, deduplicated) |
| `\seq X` | JSON array (order preserved) |
| `X \pfun Y` | JSON object (`{"key1": val1, ...}`) |
| `ZBOOL` / `ztrue` / `zfalse` | JSON boolean |
| `X \cross Y` | JSON array of length 2 |

### 10. Write Generated Files

Write all generated files to the project:

#### 10a. File Layout

```text
proofs/
  ZSpec/
    Oracle.lean          -- Lean executable oracle (new)
  lakefile.toml          -- updated with [[lean_exe]] target

oracle/                  -- new directory for oracle test harness
  abstraction.ts         -- abstraction function (user customizes)
  oracle.test.ts         -- property-based test driver
  protocol.ts            -- JSON protocol types (optional)
```

Adjust file extensions and paths for the target language:

| Language | Abstraction File | Test File | Protocol File |
|----------|------------------|-----------|---------------|
| TypeScript | `oracle/abstraction.ts` | `oracle/oracle.test.ts` | `oracle/protocol.ts` |
| Python | `oracle/abstraction.py` | `oracle/test_oracle.py` | `oracle/protocol.py` |
| Swift | `oracle/Abstraction.swift` | `oracle/OracleTests.swift` | -- |
| Kotlin | `oracle/Abstraction.kt` | `oracle/OracleTest.kt` | -- |

#### 10b. File Update Policy

- **Never overwrite** `oracle/abstraction.*` if it already exists.
  The user may have customized it. Instead, generate to
  `oracle/abstraction.generated.*` and tell the user to diff.
- **Always regenerate** `proofs/ZSpec/Oracle.lean` to match the
  current spec. Operations may have been added or removed.
- **Always regenerate** the test driver to match the current
  operation set.

### 11. Build and Verify

#### 11a. Build Lean Oracle

```bash
cd proofs && lake build oracle 2>&1
```

If the build fails, report errors. Common fixes:

| Error | Fix |
|-------|-----|
| `unknown identifier 'ToString'` | Add `instance : ToString <Type> where toString := ...` |
| `failed to synthesize Decidable` | Add boolean version of precondition |
| `unknown identifier` | Check imports in Oracle.lean |

#### 11b. Smoke Test

Run a quick smoke test to verify the oracle works:

```bash
echo '{"op": "<first-operation>", "args": {<sample-args>}}' | \
  proofs/.lake/build/bin/oracle
```

Verify the output is valid JSON and contains the expected fields.

### 12. Report Results

After generating all files, report a summary.

#### 12a. Generated Files Table

```markdown
## Oracle Test Harness

**Specification**: docs/<spec>.tex
**Target language**: TypeScript
**Sequences**: 100
**Max steps per sequence**: 20

### Generated Files

| File | Purpose | Status |
|------|---------|--------|
| `proofs/ZSpec/Oracle.lean` | Lean executable oracle | Built |
| `proofs/lakefile.toml` | Updated with oracle target | OK |
| `oracle/abstraction.ts` | Abstraction function | **Needs customization** |
| `oracle/oracle.test.ts` | Property-based test driver | Ready |
```

#### 12b. Operations Covered

```markdown
### Operations in Oracle

| # | Operation | Kind | Inputs | In Oracle |
|---|-----------|------|--------|-----------|
| 1 | Deposit | Delta | amount: nat_1 | Yes |
| 2 | Withdraw | Delta | amount: nat_1 | Yes |
| 3 | GetBalance | Xi | (none) | Yes |
| 4 | Close | Delta | (none) | Yes |
```

#### 12c. How to Run

```markdown
### How to Run

1. **Build the oracle** (if not already built):
   ```bash
   cd proofs && lake build oracle
   ```

2. **Customize the abstraction function**:
   Edit `oracle/abstraction.ts` to map your concrete state
   to the abstract state. Fields marked with TODO need your input.

3. **Implement the concrete dispatch**:
   Edit `oracle/oracle.test.ts` and fill in the TODO sections
   that call your real implementation.

4. **Run the tests**:
   ```bash
   npx jest oracle/oracle.test.ts
   ```
   (or `pytest oracle/`, `swift test`, `gradle test` as appropriate)
```

#### 12d. Customization Checklist

```markdown
### Customization Checklist

- [ ] Abstraction function maps all state fields correctly
- [ ] Free type mappings match your concrete enum values
- [ ] Given set symbolic values match your concrete identifiers
- [ ] Concrete dispatch calls your real implementation methods
- [ ] Concrete initialization matches your system's init
```

#### 12e. Next Steps

Based on the results, suggest next steps:

- If everything built: "Build the oracle, customize the abstraction
  function, and run the tests. The oracle will catch any case where
  your implementation diverges from the proven specification."
- If Lean build failed: "Fix the Lean build errors first. The most
  common issue is missing `ToString` instances for opaque types."
- If no Lean project: "Run `/z-spec:prove` first to generate the
  Lean model."

## Error Handling

| Error | Response |
|-------|----------|
| Lean not installed | "Lean 4 is not installed. Run `/z-spec:setup lean` to install via elan." |
| Lake not installed | "Lake not found. It should be included with Lean 4. Run `elan toolchain install leanprover/lean4:v4.16.0`." |
| No proofs/ directory | "No Lean project found. Run `/z-spec:prove` first to generate the Lean model." |
| Specification not found | "No Z specification found. Specify path or create one with `/z-spec:code2model`." |
| No state schemas | "No state schemas found. The oracle needs a state to track." |
| No operations | "No operation schemas found. The oracle needs operations to execute." |
| Lean model out of sync | "Warning: Lean model may not match the current specification. Consider re-running `/z-spec:prove`." |
| `lake build oracle` fails | Show errors, suggest fixes for common issues (ToString, Decidable). |
| Oracle smoke test fails | "Oracle binary produced invalid output. Check `proofs/ZSpec/Oracle.lean` for serialization errors." |
| Unsupported language | "Language not supported for oracle generation. Supported: Swift, TypeScript, Python, Kotlin." |
| Abstraction file exists | "Abstraction function already exists. Generating to `abstraction.generated.*` -- diff with your version." |

## Worked Example

Given this Z specification (`docs/counter.tex`):

```latex
\begin{zed}
[COUNTERID]
\end{zed}

\begin{axdef}
MAX\_COUNT : \nat
\where
MAX\_COUNT = 100
\end{axdef}

\begin{schema}{Counter}
value : \nat \\
limit : \nat
\where
value \leq limit \\
limit \leq MAX\_COUNT
\end{schema}

\begin{schema}{InitCounter}
Counter'
\where
value' = 0 \\
limit' = MAX\_COUNT
\end{schema}

\begin{schema}{Increment}
\Delta Counter
\where
value < limit \\
value' = value + 1 \\
limit' = limit
\end{schema}

\begin{schema}{Reset}
\Delta Counter
\where
value' = 0 \\
limit' = limit
\end{schema}

\begin{schema}{GetValue}
\Xi Counter \\
result! : \nat
\where
result! = value
\end{schema}
```

And an existing Lean project from `/z-spec:prove`, the command
generates:

**proofs/ZSpec/Oracle.lean**:

```lean
/-
  ZSpec.Oracle
  Generated from: docs/counter.tex
  Date: 2026-02-27

  Executable oracle for property-based testing.
-/

import ZSpec.State
import ZSpec.Operations

def Counter.toJson (s : Counter) : String :=
  "{\"value\": " ++ toString s.value ++
  ", \"limit\": " ++ toString s.limit ++ "}"

def increment_precondition_bool (s : Counter) : Bool :=
  s.value < s.limit

def parseAndExecute (s : Counter) (line : String) : Counter :=
  -- Simple dispatch based on operation name
  if line.containsSubstr "\"increment\"" then
    if increment_precondition_bool s then
      increment s
    else
      s
  else if line.containsSubstr "\"reset\"" then
    reset s
  else
    s  -- unknown op or getvalue (Xi): no state change

def main : IO Unit := do
  let stdin <- IO.getStdin
  let stdout <- IO.getStdout
  let mut state := initCounter
  stdout.putStrLn (Counter.toJson state)
  let mut line <- stdin.getLine
  while !line.isEmpty do
    let trimmed := line.trim
    if !trimmed.isEmpty then
      state := parseAndExecute state trimmed
      stdout.putStrLn (Counter.toJson state)
    line <- stdin.getLine
```

**Updated proofs/lakefile.toml** (appended):

```toml
[[lean_exe]]
name = "oracle"
root = "ZSpec.Oracle"
```

**oracle/abstraction.ts**:

```typescript
interface AbstractState {
  value: number;
  limit: number;
}

function abstractState(concrete: ConcreteCounter): AbstractState {
  return {
    value: concrete.value,   // direct mapping
    limit: concrete.limit,   // direct mapping
  };
}

export { AbstractState, abstractState };
```

**oracle/oracle.test.ts**:

```typescript
import fc from 'fast-check';
import { spawn } from 'child_process';
import { AbstractState, abstractState } from './abstraction';

const ORACLE_BIN = 'proofs/.lake/build/bin/oracle';

type Operation =
  | { op: 'increment' }
  | { op: 'reset' }
  | { op: 'getValue' };

const operationArb: fc.Arbitrary<Operation> = fc.oneof(
  fc.record({ op: fc.constant('increment' as const) }),
  fc.record({ op: fc.constant('reset' as const) }),
  fc.record({ op: fc.constant('getValue' as const) }),
);

// ... (full driver as in section 8a)

describe('Oracle: Counter concrete refines abstract', () => {
  it('matches Lean model for random operation sequences', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(operationArb, { minLength: 1, maxLength: 20 }),
        async (operations) => {
          const oracle = spawn(ORACLE_BIN);
          // ... execute and compare
          oracle.kill();
        },
      ),
      { numRuns: 100 },
    );
  });
});
```

Report:

```markdown
## Oracle Test Harness

**Specification**: docs/counter.tex
**Target language**: TypeScript
**Sequences**: 100
**Max steps per sequence**: 20

### Generated Files

| File | Purpose | Status |
|------|---------|--------|
| `proofs/ZSpec/Oracle.lean` | Lean executable oracle | Built |
| `proofs/lakefile.toml` | Updated with oracle target | OK |
| `oracle/abstraction.ts` | Abstraction function | **Needs customization** |
| `oracle/oracle.test.ts` | Property-based test driver | Ready |

### Operations in Oracle

| # | Operation | Kind | Inputs | In Oracle |
|---|-----------|------|--------|-----------|
| 1 | Increment | Delta | (none) | Yes |
| 2 | Reset | Delta | (none) | Yes |
| 3 | GetValue | Xi | (none) | Yes (no state change) |

### Summary

- **3 operations** covered by oracle
- **0 operations** skipped (none missing from Lean model)
- Abstraction function has **0 TODOs** (all fields map directly)
```

## Integration with Other Commands

### With /z-spec:prove

`/z-spec:prove` generates the Lean model and proves invariant
preservation. `/z-spec:oracle` turns that proven model into an
executable test oracle. The oracle is only as trustworthy as the
Lean model -- if proofs have `sorry` markers, the oracle may
accept incorrect behavior.

### With /z-spec:partition

`/z-spec:partition` derives structural test cases from the
specification using TTF tactics. `/z-spec:oracle` generates
randomized test sequences against the proven model. They are
complementary: partition tests cover specific boundary conditions
systematically; oracle tests explore the state space randomly
and can find issues that structured tests miss.

### With /z-spec:model2code

`/z-spec:model2code` generates implementation code from the spec.
`/z-spec:oracle` generates tests that verify the implementation
against the spec. Together they form a complete pipeline:
spec -> model -> code -> oracle tests.

### With /z-spec:check

Always type-check the specification before generating the oracle.
`/z-spec:check` validates Z syntax; `/z-spec:oracle` validates
behavioral conformance at runtime.

## Reference

- Z notation syntax: `reference/z-notation.md`
- Schema patterns: `reference/schema-patterns.md`
- Lean 4 type mappings: `reference/lean4-patterns.md`
- Test assertion patterns: `reference/test-patterns.md`
