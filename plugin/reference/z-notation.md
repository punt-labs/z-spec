# Z Notation Reference (fuzz.sty)

Quick reference for Z notation LaTeX commands supported by fuzz.

## Document Structure

```latex
\begin{zed} ... \end{zed}           % General Z paragraphs
\begin{schema}{Name} ... \end{schema}  % Schema definitions
\begin{axdef} ... \end{axdef}       % Axiomatic definitions
\begin{gendef}[X] ... \end{gendef}  % Generic definitions
```

## Basic Types and Sets

| Command | Symbol | Meaning |
|---------|--------|---------|
| `[NAME]` | | Given set (basic type) |
| `\nat` | ℕ | Natural numbers |
| `\num` | ℤ | Integers |
| `\power X` | ℙX | Power set |
| `\finset X` | 𝔽X | Finite subsets |
| `\emptyset` | ∅ | Empty set |

## Set Operations

| Command | Symbol | Meaning |
|---------|--------|---------|
| `\cup` | ∪ | Union |
| `\cap` | ∩ | Intersection |
| `\setminus` | \ | Set difference |
| `\subseteq` | ⊆ | Subset |
| `\subset` | ⊂ | Proper subset |
| `\in` | ∈ | Membership |
| `\notin` | ∉ | Non-membership |
| `\cross` | × | Cartesian product |
| `\bigcup` | ⋃ | Generalized union |
| `\bigcap` | ⋂ | Generalized intersection |
| `\disjoint` | disjoint | Pairwise disjoint sets |
| `A \partition S` | A partition S | A partitions S |

## Relations and Functions

| Command | Symbol | Meaning |
|---------|--------|---------|
| `\rel` | ↔ | Relation |
| `\pfun` | ⇸ | Partial function |
| `\fun` | → | Total function |
| `\pinj` | ⤔ | Partial injection |
| `\inj` | ↣ | Total injection |
| `\psurj` | ⤀ | Partial surjection |
| `\surj` | ↠ | Total surjection |
| `\bij` | ⤖ | Bijection |
| `\ffun` | ⇻ | Finite partial function |
| `\finj` | ⤕ | Finite partial injection |

## Relation Operators

| Command | Symbol | Meaning |
|---------|--------|---------|
| `\dom R` | dom R | Domain |
| `\ran R` | ran R | Range |
| `\comp` | ⨾ | Forward composition |
| `\circ` | ∘ | Backward composition |
| `\dres` | ◁ | Domain restriction |
| `\rres` | ▷ | Range restriction |
| `\ndres` | ⩤ | Domain anti-restriction |
| `\nrres` | ⩥ | Range anti-restriction |
| `\inv` | ∼ | Relational inverse |
| `R \limg A \rimg` | R⦇A⦈ | Relational image of set A |
| `\oplus` | ⊕ | Override |
| `\id X` | id X | Identity relation on X |
| `R \plus` | R⁺ | Transitive closure |
| `R \star` | R* | Reflexive-transitive closure |
| `R \bsup k \esup` | Rᵏ | Iteration (k applications) |

## Sequences

| Command | Symbol | Meaning |
|---------|--------|---------|
| `\seq X` | seq X | Finite sequences of X |
| `\seq_1 X` | seq₁ X | Non-empty sequences |
| `\iseq X` | iseq X | Injective sequences (no duplicates) |
| `\langle ... \rangle` | ⟨...⟩ | Sequence literal |
| `\cat` | ⌢ | Concatenation |
| `\dcat` | ⌢/ | Distributed concatenation |
| `\head~s` | head s | First element |
| `\tail~s` | tail s | All but first |
| `\last~s` | last s | Final element |
| `\front~s` | front s | All but last |
| `\rev~s` | rev s | Reverse |
| `\squash~f` | squash f | Compact function to sequence |
| `A \extract s` | A ↿ s | Elements at positions in A |
| `s \filter A` | s ↾ A | Keep elements in A |
| `s \prefix t` | s ⊑ t | s is prefix of t |
| `s \suffix t` | | s is suffix of t |
| `s \inseq t` | | s is segment of t |

## Bags (Multisets)

| Command | Symbol | Meaning |
|---------|--------|---------|
| `\bag X` | bag X | Bags (multisets) of X |
| `\lbag ... \rbag` | ⊎...⊎ | Bag literal |
| `B \bcount x` | B # x | Count of x in bag B |
| `x \inbag B` | x ∈ᵇ B | Bag membership |
| `\subbageq` | ⊑ᵇ | Sub-bag |
| `\uplus` | ⊎ | Bag union (add counts) |
| `\uminus` | ⊖ | Bag difference (subtract counts) |
| `\items~s` | items s | Sequence to bag |

## Logic

| Command | Symbol | Meaning |
|---------|--------|---------|
| `\land` | ∧ | Conjunction |
| `\lor` | ∨ | Disjunction |
| `\lnot` | ¬ | Negation |
| `\implies` | ⇒ | Implication |
| `\iff` | ⇔ | Equivalence |
| `\forall` | ∀ | Universal quantifier |
| `\exists` | ∃ | Existential quantifier |
| `\exists_1` | ∃₁ | Unique existence |

## Schema Notation

| Command | Meaning |
|---------|---------|
| `\Delta S` | State change (includes S and S') |
| `\Xi S` | No state change (S = S') |
| `\where` | Separates declarations from predicates |
| `x?` | Input variable |
| `x!` | Output variable |
| `x'` | After-state variable |
| `\theta S` | Binding/tuple of schema S components |

## Schema Operators

| Command | Symbol | Meaning |
|---------|--------|---------|
| `S \land T` | S ∧ T | Schema conjunction |
| `S \lor T` | S ∨ T | Schema disjunction |
| `\lnot S` | ¬S | Schema negation |
| `\pre S` | pre S | Precondition (when operation applicable) |
| `S \semi T` | S ⨟ T | Sequential composition |
| `S \pipe T` | S ≫ T | Piping (outputs to inputs) |
| `S[y/x]` | S[y/x] | Renaming (x becomes y) |
| `S \hide (x,y)` | S \ (x,y) | Hiding (existential quantification) |
| `S \project (x,y)` | S ↾ (x,y) | Projection onto components |

## Arithmetic

| Command | Symbol | Meaning |
|---------|--------|---------|
| `\div` | div | Integer division |
| `\mod` | mod | Modulo |
| `\upto` | .. | Range (1 \upto 10) |
| `\leq` | ≤ | Less than or equal |
| `\geq` | ≥ | Greater than or equal |
| `\neq` | ≠ | Not equal |

## Keywords

| Command | Meaning |
|---------|---------|
| `\LET x == e @` | Local definition |
| `\IF p \THEN e_1 \ELSE e_2` | Conditional |
| `\lambda x : T @ e` | Lambda abstraction |
| `\mu x : T \| P` | Definite description |

## Free Types

```latex
\begin{zed}
Direction ::= receive | send
Status ::= pending | active | completed
\end{zed}
```

## Common Patterns

### State Schema with Invariant
```latex
\begin{schema}{Account}
balance : \nat \\
limit : \nat
\where
balance \leq limit
\end{schema}
```

### Operation Schema
```latex
\begin{schema}{Deposit}
\Delta Account \\
amount? : \nat_1
\where
balance' = balance + amount? \\
limit' = limit
\end{schema}
```

### Initialization Schema
```latex
\begin{schema}{InitAccount}
Account'
\where
balance' = 0 \\
limit' = 1000
\end{schema}
```

## Fuzz Limitations

- No tuple projection (`.1`, `.2`) - use named schema fields instead
- No `\boolean` type - define as free type: `ZBOOL ::= ztrue | zfalse`
- No `\min`/`\max` - use conditional predicates
- Cardinality `#` on expressions can be tricky - may need reformulation

## ProB Limitations

For probcli animation and model checking:

- **Avoid B keywords**: Don't use `BOOL`, `TRUE`, `FALSE`, `true`, `false` - use `ZBOOL`, `ztrue`, `zfalse`
- **Concrete function values**: Abstract functions (e.g., `f : A \pinj B` with only domain constraints) cannot be animated - provide explicit mappings
- **Bounded integers**: Add upper bounds (`x \leq 1000`) to avoid unbounded enumeration
- **Unified Init**: Create a single `Init` schema for initialization
- **Given set cardinality**: Sets default to size 2-5 in model checking
