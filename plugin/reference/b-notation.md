# B-Method Notation Reference

Quick reference for the B Abstract Machine Notation (AMN). B shares Z's mathematical
foundations but adds a substitution language for executable specifications and a
first-class refinement chain.

## File Extensions

| Extension | Purpose | Keyword |
|-----------|---------|---------|
| `.mch` | Abstract machine | `MACHINE` |
| `.ref` | Refinement machine | `REFINEMENT` |
| `.imp` | Implementation machine | `IMPLEMENTATION` |

## Machine Structure

```b
MACHINE MachineName(parameters)
/* Optional machine parameters — deferred sets or scalar constants */

SETS
    /* Enumerated and deferred sets */
    COLOR = {red, green, blue};
    ID    /* deferred set — no values specified */

CONSTANTS
    max_count

PROPERTIES
    /* Typing and constraints on constants */
    max_count : NAT &
    max_count = 100

DEFINITIONS
    /* Macro-like text substitutions */
    is_valid(xx) == (xx : 1..max_count)

VARIABLES
    count, registry

INVARIANT
    /* Typing and state constraints — must hold after every operation */
    count : NAT &
    count <= max_count &
    registry : ID +-> NAT

INITIALISATION
    count := 0 ||
    registry := {}

OPERATIONS
    /* Operation definitions with substitution language */
    result <-- query_count =
        result := count;

    increment =
        PRE count < max_count
        THEN count := count + 1
        END;

    register(id, val) =
        PRE id : ID & val : NAT & id /: dom(registry)
        THEN registry := registry \/ {id |-> val}
        END
END
```

## Clauses (in order)

| Clause | Purpose | Required |
|--------|---------|----------|
| `MACHINE` | Machine name and parameters | Yes |
| `CONSTRAINTS` | Constraints on machine parameters | No |
| `SETS` | Enumerated and deferred sets | No |
| `CONSTANTS` | Named constants | No |
| `PROPERTIES` | Typing and constraints on constants | With CONSTANTS |
| `DEFINITIONS` | Text macros | No |
| `VARIABLES` | State variables | No |
| `INVARIANT` | Typing and state constraints | With VARIABLES |
| `INITIALISATION` | Initial substitution | With VARIABLES |
| `OPERATIONS` | Named operations | No |
| `ASSERTIONS` | Provable consequences of the invariant | No |

## Substitution Language

B operations use substitutions (not predicates). Each substitution transforms state.

| Substitution | Syntax | Meaning |
|-------------|--------|---------|
| Assignment | `x := E` | Set x to E |
| Parallel | `S1 \|\| S2` | Execute S1 and S2 simultaneously (no shared writes) |
| Sequential | `S1 ; S2` | Execute S1 then S2 |
| Precondition | `PRE P THEN S END` | Guard S with precondition P |
| Selection | `IF P THEN S1 ELSE S2 END` | Conditional |
| Case | `CASE E OF EITHER v1 THEN S1 OR v2 THEN S2 END END` | Pattern match |
| Any | `ANY x WHERE P THEN S END` | Nondeterministic choice |
| Choice | `CHOICE S1 OR S2 END` | Nondeterministic alternative |
| Select | `SELECT P1 THEN S1 WHEN P2 THEN S2 END` | Guarded commands |
| Becomes member | `x :: S` | x becomes any member of set S |
| Becomes such that | `x : (P)` | x gets a value satisfying P |
| Skip | `skip` | No-op |
| While | `WHILE P DO S INVARIANT I VARIANT V END` | Loop (implementation only) |

## Types

| B Type | Notation | Z Equivalent |
|--------|----------|-------------|
| Integer | `INT`, `NAT`, `NAT1` | `\num`, `\nat`, `\nat_1` |
| Integer range | `min..max` | `min \upto max` |
| Boolean | `BOOL` | No direct equiv (use `ZBOOL` in Z) |
| Power set | `POW(S)` | `\power S` |
| Cartesian product | `S * T` | `S \cross T` |
| Partial function | `S +-> T` | `S \pfun T` |
| Total function | `S --> T` | `S \fun T` |
| Partial injection | `S >+> T` | `S \pinj T` |
| Total injection | `S >-> T` | `S \inj T` |
| Partial surjection | `S +->> T` | `S \psurj T` |
| Total surjection | `S -->> T` | `S \surj T` |
| Bijection | `S >->> T` | `S \bij T` |
| Relation | `S <-> T` | `S \rel T` |
| Sequence | `seq(S)` | `\seq S` |
| Non-empty sequence | `seq1(S)` | `\seq_1 S` |
| Injective sequence | `iseq(S)` | `\iseq S` |
| Set of pairs | `{a \|-> b, ...}` | `\{a \mapsto b, ...\}` |

## Set and Relation Operators

| B Operator | Notation | Z Equivalent |
|-----------|----------|-------------|
| Union | `S \/ T` | `S \cup T` |
| Intersection | `S /\ T` | `S \cap T` |
| Difference | `S - T` | `S \setminus T` |
| Membership | `x : S` | `x \in S` |
| Not member | `x /: S` | `x \notin S` |
| Subset | `S <: T` | `S \subseteq T` |
| Strict subset | `S <<: T` | `S \subset T` |
| Cardinality | `card(S)` | `\# S` |
| Domain | `dom(R)` | `\dom R` |
| Range | `ran(R)` | `\ran R` |
| Domain restriction | `S <\| R` | `S \dres R` |
| Domain anti-restriction | `S <<\| R` | `S \ndres R` |
| Range restriction | `R \|> S` | `R \rres S` |
| Range anti-restriction | `R \|>> S` | `R \nrres S` |
| Override | `R1 <+ R2` | `R_1 \oplus R_2` |
| Composition | `R1 ; R2` | `R_1 \comp R_2` |
| Inverse | `R~` | `R\inv` |
| Image | `R[S]` | `R \limg S \rimg` |
| Maplet | `a \|-> b` | `a \mapsto b` |
| Empty set | `{}` | `\emptyset` |

## Predicate Logic

| B | Z Equivalent | Meaning |
|---|-------------|---------|
| `P & Q` | `P \land Q` | Conjunction |
| `P or Q` | `P \lor Q` | Disjunction |
| `not(P)` | `\lnot P` | Negation |
| `P => Q` | `P \implies Q` | Implication |
| `P <=> Q` | `P \iff Q` | Equivalence |
| `!x.(P => Q)` | `\forall x \bullet P \implies Q` | Universal |
| `#x.(P & Q)` | `\exists x \bullet P \land Q` | Existential |
| `x = y` | `x = y` | Equality |
| `x /= y` | `x \neq y` | Inequality |

## Refinement Structure

```b
REFINEMENT MachineName_r
REFINES MachineName

SETS
    /* May introduce new concrete sets */

VARIABLES
    /* Concrete variables replacing abstract ones */
    concrete_registry

INVARIANT
    /* Gluing invariant: links concrete to abstract state */
    concrete_registry : ID +-> NAT &
    concrete_registry = registry

INITIALISATION
    concrete_registry := {}

OPERATIONS
    /* Must refine every abstract operation */
    register(id, val) =
        PRE id : ID & val : NAT & id /: dom(concrete_registry)
        THEN concrete_registry := concrete_registry \/ {id |-> val}
        END
END
```

## Implementation Structure

```b
IMPLEMENTATION MachineName_i
REFINES MachineName_r

/* IMPORTS other machines for reuse */
IMPORTS ArrayMachine(100)

VARIABLES
    /* Concrete implementation variables */

INVARIANT
    /* Links to refinement variables */

INITIALISATION
    /* Must be deterministic */

OPERATIONS
    /* Must be deterministic — no ANY, CHOICE, or SELECT */
END
```

## probcli Commands for B

```bash
# Type-check a machine
probcli Machine.mch

# Initialize and parse
probcli Machine.mch -init

# Animate
probcli Machine.mch -animate 20

# Model-check
probcli Machine.mch -model_check

# Check refinement
probcli Machine.mch -refcheck Refinement.ref

# Check assertions
probcli Machine.mch -cbc_assertions

# Check deadlock freedom
probcli Machine.mch -cbc_deadlock
```
