---
description: Generate code from a Z specification
argument-hint: "[spec.tex] [language: swift, typescript, python, kotlin]"
allowed-tools: Bash(fuzz:*), Bash(which:*), Read, Glob, Grep, Write
---

# /z model2code - Model to Code

Generate implementation code and unit tests from a Z specification.

## Usage

```
/z model2code [spec.tex] [language]
```

**Arguments:**
- `spec.tex` - Z specification file (default: search in docs/)
- `language` - Target: swift, typescript, python, kotlin (default: detect from project)

## Workflow

### Step 1: Validate the Specification

Before generating code, type-check the specification with fuzz:

```bash
fuzz -t <spec.tex>
```

If fuzz reports errors, fix them first. Code generation from invalid specs produces invalid code.

### Step 2: Detect Target Language

If no language specified, detect from project files:

| File Present | Language |
|--------------|----------|
| `Package.swift`, `*.xcodeproj` | Swift |
| `package.json`, `tsconfig.json` | TypeScript |
| `pyproject.toml`, `setup.py`, `requirements.txt` | Python |
| `build.gradle.kts`, `pom.xml` | Kotlin |

### Step 3: Generate Code

Read the Z specification and translate each construct to idiomatic code for the target language.

## Translation Principles

### State Schemas → Classes/Structs

Z state schemas become data types with properties:

```latex
\begin{schema}{Account}
balance : \num \\
status : Status
\where
balance \geq 0 \lor status = suspended
\end{schema}
```

**Swift:**
```swift
struct Account {
    var balance: Int
    var status: Status

    var isValid: Bool {
        balance >= 0 || status == .suspended
    }
}
```

**TypeScript:**
```typescript
interface Account {
    balance: number;
    status: Status;
}

function isValidAccount(a: Account): boolean {
    return a.balance >= 0 || a.status === Status.Suspended;
}
```

### Free Types → Enums

```latex
\begin{zed}
Status ::= pending | active | suspended | closed
\end{zed}
```

**Swift:**
```swift
enum Status {
    case pending, active, suspended, closed
}
```

**TypeScript:**
```typescript
enum Status {
    Pending = "pending",
    Active = "active",
    Suspended = "suspended",
    Closed = "closed"
}
```

### Given Sets → Type Aliases or Opaque Types

```latex
\begin{zed}
[USERID, SESSIONID]
\end{zed}
```

**Swift:**
```swift
typealias UserID = String  // Or UUID, depending on context
typealias SessionID = String
```

**TypeScript:**
```typescript
type UserID = string;
type SessionID = string;
// Or use branded types for type safety:
type UserID = string & { readonly brand: unique symbol };
```

### Init Schemas → Initializers/Constructors

```latex
\begin{schema}{InitAccount}
Account'
\where
balance' = 0 \\
status' = pending
\end{schema}
```

**Swift:**
```swift
extension Account {
    init() {
        self.balance = 0
        self.status = .pending
    }
}
```

### Operations with Delta → Mutating Methods

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

**Swift:**
```swift
extension Account {
    mutating func deposit(amount: Int) {
        precondition(amount > 0, "Amount must be positive")
        guard status == .active else { return }
        balance += amount
    }
}
```

### Operations with Xi → Non-Mutating/Query Methods

```latex
\begin{schema}{GetBalance}
\Xi Account \\
result! : \num
\where
result! = balance
\end{schema}
```

**Swift:**
```swift
extension Account {
    func getBalance() -> Int {
        return balance
    }
}
```

### Type Mappings

| Z Type | Swift | TypeScript | Python | Kotlin |
|--------|-------|------------|--------|--------|
| `\nat` | `Int` (with `>= 0` check) | `number` | `int` | `Int` |
| `\nat_1` | `Int` (with `> 0` check) | `number` | `int` | `Int` |
| `\num` | `Int` | `number` | `int` | `Int` |
| `X \pfun Y` | `[X: Y]` | `Map<X, Y>` | `dict[X, Y]` | `Map<X, Y>` |
| `X \fun Y` | `[X: Y]` (total) | `Map<X, Y>` | `dict[X, Y]` | `Map<X, Y>` |
| `\power X` | `Set<X>` | `Set<X>` | `set[X]` | `Set<X>` |
| `\seq X` | `[X]` | `X[]` | `list[X]` | `List<X>` |
| `X \cross Y` | `(X, Y)` | `[X, Y]` | `tuple[X, Y]` | `Pair<X, Y>` |

### Handling Inputs and Outputs

| Z Convention | Code Pattern |
|--------------|--------------|
| `x?` (input) | Method parameter |
| `x!` (output) | Return value |
| Multiple outputs | Return tuple or result struct |

### Preconditions

Z preconditions become guard statements or assertions:

```latex
amount? \leq balance   % Precondition in Z
```

**Swift:**
```swift
guard amount <= balance else {
    // Handle precondition failure
    return
}
```

**TypeScript:**
```typescript
if (amount > balance) {
    throw new Error("Insufficient balance");
}
```

## Test Generation

### Invariants → Unit Tests

Each schema predicate becomes one or more test cases:

| Z Invariant | Test Strategy |
|-------------|---------------|
| `balance \geq 0` | Test valid (0, 1, 100), test that negative fails validation |
| `correct \leq attempts` | Test equal case, test invalid (correct > attempts) |
| `level \geq 1 \land level \leq 26` | Test boundaries (1, 26), test invalid (0, 27) |
| `status = active \implies balance \geq 0` | Test implication: active+negative should fail |

### Example Test Generation

For the Account schema above:

**Swift (XCTest):**
```swift
final class AccountTests: XCTestCase {

    // Invariant: balance >= 0 OR status == suspended

    func testValidAccount_positiveBalance() {
        let account = Account(balance: 100, status: .active)
        XCTAssertTrue(account.isValid)
    }

    func testValidAccount_zeroBalance() {
        let account = Account(balance: 0, status: .active)
        XCTAssertTrue(account.isValid)
    }

    func testValidAccount_negativeBalanceWhenSuspended() {
        let account = Account(balance: -50, status: .suspended)
        XCTAssertTrue(account.isValid)  // Allowed when suspended
    }

    func testInvalidAccount_negativeBalanceWhenActive() {
        let account = Account(balance: -50, status: .active)
        XCTAssertFalse(account.isValid)
    }

    // Init schema tests

    func testInitAccount() {
        let account = Account()
        XCTAssertEqual(account.balance, 0)
        XCTAssertEqual(account.status, .pending)
        XCTAssertTrue(account.isValid)
    }

    // Operation tests

    func testDeposit_increasesBalance() {
        var account = Account(balance: 100, status: .active)
        account.deposit(amount: 50)
        XCTAssertEqual(account.balance, 150)
    }

    func testDeposit_requiresActiveStatus() {
        var account = Account(balance: 100, status: .suspended)
        account.deposit(amount: 50)
        XCTAssertEqual(account.balance, 100)  // Unchanged
    }
}
```

### Test Categories

Generate tests for:

1. **Valid States** - States that satisfy all invariants
2. **Boundary Conditions** - Edge cases at constraint boundaries
3. **Invariant Violations** - States that should fail validation
4. **Operation Preconditions** - Verify operations check their guards
5. **Operation Effects** - Verify operations produce correct after-states
6. **Init Validity** - Verify initialized state satisfies invariants

## Output Structure

Generate two files:

1. **Model File** - Types and operations
   - `<Name>.swift` / `<name>.ts` / `<name>.py` / `<Name>.kt`

2. **Test File** - Unit tests for invariants and operations
   - `<Name>Tests.swift` / `<name>.test.ts` / `test_<name>.py` / `<Name>Test.kt`

## Example

```
/z generate docs/account.tex swift
```

This will:
1. Run `fuzz -t docs/account.tex` to validate
2. Parse the Z specification
3. Generate `Account.swift` with types and methods
4. Generate `AccountTests.swift` with invariant and operation tests

## Notes

- Generated code is a starting point. Review and adapt to project conventions.
- Complex Z constructs (schema calculus, generics) may need manual translation.
- Invariants become `isValid` computed properties; consider property wrappers for automatic enforcement.
- For large specs, generate incrementally by schema rather than all at once.
