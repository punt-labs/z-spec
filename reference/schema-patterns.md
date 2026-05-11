# Z Schema Patterns

Common patterns for modeling stateful systems in Z.

## Document Structure

A well-organized Z specification follows this order:

1. **Introduction** - Brief description of the system
2. **Basic Types** - Given sets for entities without internal structure
3. **Free Types** - Enumerations and tagged unions
4. **Global Constants** - System-wide configuration values
5. **State Schemas** - Core data structures with invariants
6. **Initialization Schemas** - Valid initial states
7. **Operation Schemas** - State transitions
8. **System Invariants** - Summary of key properties

## Basic Types

Use given sets for entities where internal structure is irrelevant:

```latex
\begin{zed}
[USERID, SESSIONID, TIMESTAMP]
\end{zed}
```

Good candidates:
- Identifiers (user IDs, session IDs, transaction IDs)
- Opaque handles (file handles, connection handles)
- Abstract time (timestamps, dates)
- External references (URLs, paths)

## Free Types for Enumerations

```latex
\begin{zed}
Status ::= pending | active | completed | cancelled
Role ::= admin | moderator | user | guest
\end{zed}
```

For booleans (fuzz doesn't have built-in boolean):
```latex
% Use ZBOOL to avoid ProB/B keyword conflicts
\begin{zed}
ZBOOL ::= ztrue | zfalse
\end{zed}
```

## State Schema Patterns

### Simple Entity with Invariant

```latex
\begin{schema}{Account}
accountId : ACCOUNTID \\
balance : \num \\
status : Status
\where
status = active \implies balance \geq 0
\end{schema}
```

### Entity with Bounded Values

```latex
\begin{schema}{Settings}
volume : \nat \\
brightness : \nat
\where
volume \leq 100 \\
brightness \leq 100
\end{schema}
```

### Entity with Related Counts

```latex
\begin{schema}{Statistics}
attempts : \nat \\
successes : \nat \\
failures : \nat
\where
successes \leq attempts \\
failures \leq attempts \\
successes + failures \leq attempts
\end{schema}
```

### Collection with Constraints

```latex
\begin{schema}{UserRegistry}
users : USERID \pfun UserProfile \\
activeUsers : \power USERID
\where
activeUsers \subseteq \dom users
\end{schema}
```

### Ordered History

```latex
\begin{schema}{EventLog}
events : \seq Event \\
lastProcessed : \nat
\where
lastProcessed \leq \# events
\end{schema}
```

### Composed State (Schema Inclusion)

```latex
\begin{schema}{Application}
currentUser : USERID \\
session : Session \\
settings : Settings
\where
session.userId = currentUser
\end{schema}
```

## Initialization Patterns

### Simple Init

```latex
\begin{schema}{InitAccount}
Account'
\where
balance' = 0 \\
status' = pending
\end{schema}
```

### Init with Constraints (membership test)

```latex
\begin{schema}{InitSettings}
Settings'
\where
volume' = 50 \\
brightness' = 75
\end{schema}
```

## Operation Schema Patterns

### State-Changing Operation (Delta)

```latex
\begin{schema}{Deposit}
\Delta Account \\
amount? : \nat_1
\where
status = active \\
balance' = balance + amount? \\
status' = status \\
accountId' = accountId
\end{schema}
```

### Query Operation (Xi - no change)

```latex
\begin{schema}{GetBalance}
\Xi Account \\
result! : \num
\where
result! = balance
\end{schema}
```

### Conditional Operation

```latex
\begin{schema}{Withdraw}
\Delta Account \\
amount? : \nat_1
\where
status = active \\
amount? \leq balance \\
balance' = balance - amount? \\
status' = status
\end{schema}
```

### Operation with Boolean Outcome

```latex
\begin{schema}{TryWithdraw}
\Delta Account \\
amount? : \nat_1 \\
success! : ZBOOL
\where
(amount? \leq balance \land
    balance' = balance - amount? \land
    success! = ztrue) \lor
(amount? > balance \land
    balance' = balance \land
    success! = zfalse)
\end{schema}
```

### Operation Adding to Collection

```latex
\begin{schema}{AddUser}
\Delta UserRegistry \\
newUser? : USERID \\
profile? : UserProfile
\where
newUser? \notin \dom users \\
users' = users \cup \{ newUser? \mapsto profile? \} \\
activeUsers' = activeUsers
\end{schema}
```

### Operation Removing from Collection

```latex
\begin{schema}{RemoveUser}
\Delta UserRegistry \\
userId? : USERID
\where
userId? \in \dom users \\
users' = \{ userId? \} \ndres users \\
activeUsers' = activeUsers \setminus \{ userId? \}
\end{schema}
```

### Operation with Override (Update)

```latex
\begin{schema}{UpdateProfile}
\Delta UserRegistry \\
userId? : USERID \\
newProfile? : UserProfile
\where
userId? \in \dom users \\
users' = users \oplus \{ userId? \mapsto newProfile? \} \\
activeUsers' = activeUsers
\end{schema}
```

## Derived Functions

### Abbreviation for Common Computations

```latex
\begin{zed}
accuracy == (\lambda stats : Statistics @
    \IF stats.attempts = 0
    \THEN 0
    \ELSE (stats.successes * 100) \div stats.attempts)
\end{zed}
```

### Generic Helper Functions

```latex
\begin{gendef}[X, Y]
fst : X \cross Y \fun X \\
snd : X \cross Y \fun Y
\where
\forall a : X; b : Y @ fst(a, b) = a \\
\forall a : X; b : Y @ snd(a, b) = b
\end{gendef}
```

## Axiomatic Definitions for Constants

```latex
\begin{axdef}
maxRetries : \nat \\
timeout : \nat
\where
maxRetries = 3 \\
timeout = 30000
\end{axdef}
```

## Tips for Fuzz Compatibility

1. **Avoid `#` on complex expressions** - compute cardinality indirectly
2. **Use partial injection (`\pinj`) for unique mappings**
3. **Define ZBOOL as free type** - fuzz has no built-in boolean
4. **Use schema inclusion** rather than tuple projection
5. **Test with `fuzz -t file.tex`** to catch type errors early
6. **Frame all state changes** - explicitly state what doesn't change

## Tips for ProB Compatibility

To create specifications that can be animated and model-checked with probcli:

### 1. Avoid B Keyword Conflicts

ProB uses B language internally. These names conflict:
- `BOOL`, `TRUE`, `FALSE`, `true`, `false`, `bool`
- `INT`, `NAT`, `STRING`

Use alternatives: `ZBOOL`, `ztrue`, `zfalse`

### 2. Provide Concrete Function Values

Abstract functions cannot be animated. Instead of:
```latex
\begin{axdef}
mapping : \nat_1 \pinj ITEM
\where
\dom mapping = 1 \upto 5
\end{axdef}
```

Provide explicit values:
```latex
\begin{axdef}
mapping : \nat_1 \pinj ITEM
\where
mapping = \{ 1 \mapsto item1, 2 \mapsto item2, 3 \mapsto item3,
             4 \mapsto item4, 5 \mapsto item5 \}
\end{axdef}
```

### 3. Add Upper Bounds to Integers

Unbounded integers cause "Unbounded enumeration" warnings:
```latex
% BAD - causes enumeration issues
count : \nat

% GOOD - bounded for finite exploration
count : \nat
\where
count \leq 1000
```

### 4. Create Unified Init Schema

ProB expects a schema named `Init` for initialization:
```latex
\begin{schema}{Init}
State'
\where
users' = \emptyset \\
count' = 0 \\
status' = pending
\end{schema}
```

### 5. Flatten State—No Nested Schema Types

ProB cannot initialize nested schema types. This fails:

```latex
% BAD - ProB fails during initialization
\begin{schema}{StudentProgress}
schedule : PracticeSchedule  % Nested schema type
\end{schema}

\begin{schema}{Init}
StudentProgress'
\where
schedule'.interval = 1  % ProB can't resolve dot notation on primed nested schema
\end{schema}
```

Flatten everything into one state schema:

```latex
% GOOD - ProB can animate
\begin{schema}{State}
receiveLevel : \nat \\
interval : \nat \\  % Moved from PracticeSchedule
streak : \nat
\where
...
\end{schema}

\begin{schema}{Init}
State'
\where
receiveLevel' = 1 \\
interval' = 1 \\
streak' = 0
\end{schema}
```

### 6. Bound Input Variables

Inputs without upper bounds cause infinite enumeration:

```latex
% BAD - probcli enumerates 90..infinity
accuracy? : \nat
\where
accuracy? \geq 90

% GOOD - finite range
accuracy? : \nat
\where
accuracy? \geq 90 \\
accuracy? \leq 100
```

### 7. Design for Small Cardinalities

Given sets default to small sizes (2-5) in model checking. Ensure invariants hold with small sets:
```bash
probcli spec.tex -model_check -p DEFAULT_SETSIZE 2
```

### 8. Bound Collection Cardinality

Every `\finset` and `\pfun` over given sets needs a `#` constraint via axdef constants. Without bounds, probcli enumerates all possible subsets/partial functions, causing silent hangs.

```latex
% BAD - unbounded, probcli hangs at large set sizes
members : \finset NAME

% GOOD - bounded via axdef constant
\begin{axdef}
maxMembers : \nat
\where
maxMembers = 3
\end{axdef}

members : \finset NAME
\where
\# members \leq maxMembers
```

### 9. Schemas Instead of Tuples

Use named schemas with fields instead of cross products. probcli cannot apply `first`/`second` to triples or larger tuples.

```latex
% BAD - cross product triple
assignments : \finset (NAME \cross HANDLE \cross Relation)

% GOOD - named schema
\begin{schema}{Assignment}
aName : NAME \\
aHandle : HANDLE \\
aRelation : Relation
\end{schema}

assignments : \finset Assignment
```

### 10. Scope All Quantifiers

Quantify over sets from state, never over bare given types. `\forall n : NAME` enumerates the entire given type; `\forall n : members` enumerates only the current state.

```latex
% BAD - enumerates all of NAME
\forall n : NAME @ n \in members \implies n \in \dom handles

% GOOD - scoped to state
\forall n : members @ n \in \dom handles
```

### 11. Operation Bounds

Operations that grow collections must include `\# collection < maxBound` in preconditions. Without this, the operation silently fails when the state invariant's bound is reached.

```latex
% BAD - no capacity check
name? \notin members \\
members' = members \cup \{ name? \}

% GOOD - explicit bound
name? \notin members \\
\# members < maxMembers \\
members' = members \cup \{ name? \}
```

### 12. No Underscored Constructors

Free type constructors with underscores (`reports\_to`) work in fuzz but may cause issues in probcli's B translation. Use camelCase or concatenated names.

```latex
% BAD - underscore in constructor
Relation ::= reports\_to | mentors | peers

% GOOD - camelCase
Relation ::= reportsTo | mentors | peers
```

### 13. No \mu for Record Construction

`\mu Schema` for definite description may not translate correctly in probcli. Use explicit set comprehension instead.

```latex
% BAD - \mu may fail in probcli
assignments' = assignments \cup
    \{ \mu Assignment | aName = name? \land aHandle = handle? \}

% GOOD - explicit comprehension
assignments' = assignments \cup
    \{ a : Assignment | a.aName = name? \land a.aHandle = handle? \}
```

## Sequences (Expanded)

### Sequence Types

| Type | Meaning | Equivalent |
|------|---------|------------|
| `\seq X` | Finite sequences of X | `\{ f : \nat_1 \pfun X \| \dom f = 1 \upto \# f \}` |
| `\seq_1 X` | Non-empty sequences | `\{ s : \seq X \| s \neq \langle \rangle \}` |
| `\iseq X` | Injective sequences (no duplicates) | `\{ s : \seq X \| s \in \nat_1 \pinj X \}` |

### Sequence Literals and Construction

```latex
% Empty sequence
\langle \rangle

% Explicit sequence
\langle a, b, c \rangle

% Sequence from 1..n
1 \upto 5 = \{ 1, 2, 3, 4, 5 \}  % This is a set, not a sequence

% Convert set to sequence (when order doesn't matter)
% Use squash on a relation
```

### Sequence Operations

| Operation | Syntax | Type | Description |
|-----------|--------|------|-------------|
| Length | `\# s` | `\nat` | Number of elements |
| Head | `\head~s` | `X` | First element (s non-empty) |
| Last | `\last~s` | `X` | Final element (s non-empty) |
| Tail | `\tail~s` | `\seq X` | All but first element |
| Front | `\front~s` | `\seq X` | All but last element |
| Concatenation | `s \cat t` | `\seq X` | Join two sequences |
| Reverse | `\rev~s` | `\seq X` | Reverse order |
| Distributed concat | `\dcat~ss` | `\seq X` | Flatten sequence of sequences |

### Sequence Filtering and Extraction

| Operation | Syntax | Description |
|-----------|--------|-------------|
| Extraction | `A \extract s` | Elements at positions in A |
| Filtering | `s \filter A` | Elements whose values are in A |
| Squash | `\squash~f` | Compact a finite function to a sequence |

```latex
% Extract positions 2 and 4 from sequence
\{ 2, 4 \} \extract \langle a, b, c, d, e \rangle = \langle b, d \rangle

% Filter to keep only vowels
\langle c, a, t \rangle \filter \{ a, e, i, o, u \} = \langle a \rangle
```

### Sequence Predicates

| Predicate | Syntax | Meaning |
|-----------|--------|---------|
| Prefix | `s \prefix t` | s is a prefix of t |
| Suffix | `s \suffix t` | s is a suffix of t |
| Segment | `s \inseq t` | s is a contiguous segment of t |

```latex
\langle a, b \rangle \prefix \langle a, b, c \rangle  % True
\langle b, c \rangle \suffix \langle a, b, c \rangle  % True
\langle b \rangle \inseq \langle a, b, c \rangle      % True
```

### Sequence Patterns in Practice

```latex
% Event log with bounded history
\begin{schema}{EventLog}
events : \seq Event \\
maxHistory : \nat
\where
\# events \leq maxHistory
\end{schema}

% Append with bounded size
\begin{schema}{LogEvent}
\Delta EventLog \\
newEvent? : Event
\where
\# events < maxHistory \\
events' = events \cat \langle newEvent? \rangle \\
maxHistory' = maxHistory
\end{schema}

% Queue operations
\begin{schema}{Dequeue}
\Delta Queue \\
item! : Item
\where
items \neq \langle \rangle \\
item! = \head~items \\
items' = \tail~items
\end{schema}
```

## Bags (Multisets)

Bags allow duplicate elements with counts.

### Bag Types and Literals

| Syntax | Meaning |
|--------|---------|
| `\bag X` | Bags of elements from X |
| `\lbag a, a, b \rbag` | Bag containing two a's and one b |
| `\lbag \rbag` | Empty bag |

A bag is equivalent to a function from elements to their counts: `\bag X == X \pfun \nat_1`

### Bag Operations

| Operation | Syntax | Description |
|-----------|--------|-------------|
| Count | `B \bcount x` | Number of occurrences of x in B |
| Membership | `x \inbag B` | x occurs at least once in B |
| Sub-bag | `B_1 \subbageq B_2` | B_1 counts ≤ B_2 counts for all elements |
| Union | `B_1 \uplus B_2` | Sum of counts |
| Difference | `B_1 \uminus B_2` | Subtract counts (floor at 0) |
| Items | `\items~s` | Convert sequence to bag |

```latex
% Inventory as bag of products
\begin{schema}{Inventory}
stock : \bag PRODUCT
\end{schema}

% Add items to inventory
\begin{schema}{Restock}
\Delta Inventory \\
items? : \bag PRODUCT
\where
stock' = stock \uplus items?
\end{schema}

% Remove items (with availability check)
\begin{schema}{Sell}
\Delta Inventory \\
items? : \bag PRODUCT
\where
items? \subbageq stock \\
stock' = stock \uminus items?
\end{schema}
```

## Schema Operators

### Schema Conjunction and Disjunction

Schemas can be combined with logical operators:

```latex
% Conjunction - both must hold
TotalOperation == SuccessCase \land ErrorCase

% Disjunction - one or the other
RobustOperation == NormalCase \lor ErrorHandling
```

### Schema Composition

| Operator | Syntax | Meaning |
|----------|--------|---------|
| Sequential | `S \semi T` | Do S, then T (hide intermediate state) |
| Piping | `S \pipe T` | Outputs of S feed inputs of T |

```latex
% Sequential: authenticate then perform action
SecureAction == Authenticate \semi PerformAction

% Piping: validate input then process
ValidatedProcess == ValidateInput \pipe ProcessData
% Outputs validate! become inputs process?
```

### Schema Precondition

The precondition operator extracts when an operation is applicable:

```latex
\pre Withdraw  % States where Withdraw can execute
```

Useful for defining total operations:
```latex
WithdrawOK == \pre Withdraw \land Withdraw
WithdrawFail == \lnot \pre Withdraw \land \Xi Account \land error! = insufficient
TotalWithdraw == WithdrawOK \lor WithdrawFail
```

### Schema Renaming

Rename components within a schema:

```latex
% Rename x to y throughout schema S
S[y/x]

% Example: create a "before" version
AccountBefore == Account[balanceBefore/balance, statusBefore/status]
```

### Schema Hiding

Hide (existentially quantify) components:

```latex
% Hide internal details
PublicInterface == FullSchema \hide (internalState, helperVar)
```

### Schema Projection

Project onto specific components:

```latex
% Project schema to just balance and status fields
AccountSummary == Account \project (balance, status)
```

## Theta Expressions

Theta (`\theta`) binds schema components into a tuple/record:

```latex
% If Account has balance, status:
\theta Account = (balance, status)  % conceptually

% Use in operations to capture before/after state
\begin{schema}{SaveSnapshot}
\Xi Account \\
snapshot! : Account
\where
\theta snapshot! = \theta Account
\end{schema}
```

Common pattern for "get current state":
```latex
currentAccount! = \theta Account
```

## Let and Mu Expressions

### Let - Local Definitions

```latex
\LET x == e @ P
% Defines x as e within predicate P

% Example: compute intermediate value
\begin{schema}{ComputeBonus}
salary : \nat \\
bonus! : \nat
\where
\LET rate == salary \div 10 @ bonus! = rate * 2
\end{schema}
```

### Mu - Definite Description

The unique value satisfying a predicate:

```latex
\mu x : T | P
% The unique x of type T satisfying P

% Example: find the user with a given ID
foundUser = \mu u : User | u.id = targetId
```

Use with care—requires exactly one value to exist.

## Disjoint and Partition

### Disjoint Sets

```latex
\disjoint \langle A, B, C \rangle
% A, B, C have no elements in common
% Equivalent to: A \cap B = \emptyset \land B \cap C = \emptyset \land A \cap C = \emptyset
```

### Partition

```latex
\langle A, B, C \rangle \partition S
% A, B, C are disjoint AND their union equals S

% Example: user roles partition all users
\langle admins, moderators, regularUsers \rangle \partition allUsers
```

## Advanced Relation Operators

### Transitive Closure

| Operator | Syntax | Meaning |
|----------|--------|---------|
| Transitive closure | `R \plus` | One or more R steps |
| Reflexive-transitive | `R \star` | Zero or more R steps |
| Iteration | `R \bsup k \esup` | Exactly k applications of R |

```latex
% Ancestor relation from parent
ancestor == parent \plus

% Reachable in zero or more steps
reachable == edge \star

% Exactly 3 hops
threeHops == link \bsup 3 \esup
```

### Identity Relation

```latex
\id X  % Identity relation on set X
% \id X = \{ x : X @ x \mapsto x \}
```

### Relational Image

```latex
R \limg A \rimg  % Image of set A through relation R
% All y where (x, y) in R for some x in A

% Example: all reports of a set of managers
directReports \limg seniorManagers \rimg
```

## Summary: Matching Z Constructs to Code

| Z Construct | Typical Code Pattern |
|-------------|---------------------|
| State schema | Class/struct with properties |
| Schema predicate | `isValid` computed property or validation method |
| `\Delta S` | Mutating method |
| `\Xi S` | Non-mutating/query method |
| Init schema | Default initializer/constructor |
| Free type | Enum |
| Given set | Type alias or opaque type |
| `\pfun` | Dictionary/Map |
| `\power` | Set |
| `\seq` | Array/List |
| `\bag` | Dictionary with counts, or Counter type |
| Precondition | Guard statement or assertion |
| `x?` input | Method parameter |
| `x!` output | Return value |
| Schema disjunction | Method with branching logic or error result |
| `\theta S` | Snapshot/copy of current state |
