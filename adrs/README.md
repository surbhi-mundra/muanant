# ADRs (Architecture Decision Records)

We use ADRs to record every architectural decision in SOVEREIGN: the
context, the options considered, the decision, and the consequences. This
makes the *why* durable — code shows what was decided; ADRs show why.

## Format

Each ADR follows:

```
# NNN. Title
Date: YYYY-MM-DD
Status: Proposed | Accepted | Superseded by NNN | Deprecated

## Context
(Why is this decision needed? What forces are at play?)

## Options considered
### Option A
- Pros:
- Cons:

### Option B
- Pros:
- Cons:

## Decision
(What we chose.)

## Reason
(Why we chose it — what tipped the balance.)

## Consequences
- Positive:
- Negative:
- Neutral:

## References
(Links to specs, prior ADRs, external docs.)
```

## Index

- [0001 — Record architecture decisions](0001-record-architecture-decisions.md) (Accepted)
- [0002 — Model Gateway abstraction](0002-model-gateway-abstraction.md) (Accepted)
- [0003 — Retrieved documents are data, not instructions](0003-retrieved-doc-as-data-not-instruction.md) (Accepted)
