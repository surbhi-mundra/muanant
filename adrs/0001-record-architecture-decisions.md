# 0001. Record architecture decisions

Date: 2026-10-09
Status: Accepted

## Context

SOVEREIGN is a multi-phase project (14 phases, ~months of work) being built
by a coding agent across many sessions. Without a durable record of *why*
each architectural decision was made, future sessions risk:

- Reversing a decision without understanding the forces that led to it.
- Repeatedly re-debating the same question ("why LangGraph not custom?").
- Introducing dependencies that conflict with earlier choices.
- Drift between the documented architecture and the implemented one.

Code shows *what* was decided; it does not show *why*. We need a lightweight
artifact that captures the context, options, decision, and consequences —
durable across sessions and human-readable.

## Options considered

### Option A — Inline comments in code
- Pros: Zero overhead; lives next to the code.
- Cons: Only visible if you're already in the file; no index; no history;
  no place for options-we-didn't-pick; comments rot faster than code.

### Option B — A single ARCHITECTURE.md
- Pros: One file to read.
- Cons: Becomes a giant over time; decisions and rationale get muddled;
  hard to evolve individual decisions without rewriting the whole doc.

### Option C — ADRs (Architecture Decision Records)
- Pros: One short doc per decision; immutable once accepted (supersession
  is a new ADR); standard format; indexable; lightweight to write.
- Cons: Slight overhead per decision; requires discipline to actually write
  them; another directory to maintain.

### Option D — Wiki / Confluence / external tool
- Pros: Rich formatting.
- Cons: Lives outside the repo → drifts from code; not versioned with the
  code; not readable offline / in air-gapped prod environments.

## Decision

Adopt **Option C — ADRs** in `adrs/`, following the format documented in
`adrs/README.md`. ADRs are plain Markdown, versioned with the code, and
never edited after acceptance (supersession is a new ADR that references
the old one).

## Reason

ADRs are the standard practice for exactly this situation: a long-running
project with many decisions, multiple contributors (including AI agents),
and a need for durable rationale. Option A and B fail the "durable why"
test; Option D fails the "versioned with code" test.

The format forces the writer to enumerate alternatives, which surfaces
assumptions that would otherwise go unstated. The immutability rule means
you can read an old ADR and trust it represents what was decided at the
time, even if the decision was later superseded.

## Consequences

- Positive: every architectural decision has a paper trail; future sessions
  (human or AI) can understand the why, not just the what.
- Positive: forces the author to enumerate alternatives — surfaces
  assumptions.
- Negative: slight overhead per decision. Mitigation: keep ADRs short
  (1–2 pages each).
- Neutral: ADRs are append-only after acceptance; supersession is a new ADR.

## References

- Michael Nygard's original ADR article: https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions
- MADR (Markdown ADR) template: https://adr.github.io/madr/
