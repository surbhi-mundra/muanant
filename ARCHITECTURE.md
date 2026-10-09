# SOVEREIGN — Architecture

This document describes the target architecture and the Phase 1 contract
surface. It is the authoritative reference for how the system fits together;
subsystem docs in `docs/` elaborate on individual pieces.

## 1. Layered design

```
┌──────────────────────────────────────────────────────────────────────┐
│  WORKBENCH (Next.js)  — upload, chat, citations, agents, approvals,  │
│                         audit, admin                                  │
└───────────────┬──────────────────────────────────────────────────────┘
                │  REST/WS (JSON, typed) + JWT
┌───────────────▼──────────────────────────────────────────────────────┐
│  API LAYER (FastAPI)  — auth, RBAC, request ID, rate limit, OpenAPI  │
└───────────────┬──────────────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────────────┐
│  ORCHESTRATION (LangGraph supervisor)  — intent → decompose → route  │
│   Agents: Supervisor | DocIntel | Vision | RAG | Research |          │
│           EvidenceVerify | Risk | Deliverable                         │
│   Shared typed State, checkpointer, HITL interrupts                   │
└───────────────┬──────────────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────────────┐
│  CAPABILITIES (domain services)                                       │
│   ingestion │ parsing │ chunking │ retrieval │ reranking │            │
│   evidence  │ risk    │ deliverables │ audit │ approvals              │
└───────────────┬──────────────────────────────────────────────────────┘
                │  depends ONLY on interfaces
┌───────────────▼──────────────────────────────────────────────────────┐
│  MODEL GATEWAY  (interfaces + adapters)                               │
│   TextLLM   →  vLLM │ Ollama │ TGI │ transformers (mock for dev)      │
│   VisionLLM →  vLLM (multimodal) │ transformers (mock)                │
│   EmbeddingModel → sentence-transformers │ Text Embeddings Inference  │
│   Reranker  →  cross-encoders │ ColBERT/ColPali                        │
│   OCR       →  Tesseract │ Surya │ PaddleOCR                           │
└───────────────┬──────────────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────────────┐
│  STORAGE                                                              │
│   PostgreSQL (metadata, audit, approvals, workflow state, RLS)        │
│   Qdrant (vectors; embedded in dev, server in prod)                   │
│   Object store (document blobs, encrypted; filesystem in dev)         │
└──────────────────────────────────────────────────────────────────────┘

CROSS-CUTTING:  security (authN/Z, egress, sandbox) │ audit │ observability
                (structured logs, OTEL traces, metrics) │ config │ policy
```

Each layer depends only on the layer below it and on cross-cutting concerns
via injected interfaces — never on concrete adapters.

## 2. The ModelGateway (model-agnosticism guarantee)

The architectural keystone. Every agent and capability asks the gateway for
a *capability* (`text`, `vision`, `embedding`, `reranker`, `ocr`) and
receives whatever adapter is wired in `configs/models.yaml`.

```python
# sovereign/models/schemas.py
class TextLLM(Protocol):
    async def complete(self, req: LLMRequest) -> LLMResponse: ...
    def stream(self, req: LLMRequest) -> AsyncIterator[LLMStreamChunk]: ...

class VisionLLM(Protocol):
    async def describe(self, req: VisionRequest) -> VisionResponse: ...

class EmbeddingModel(Protocol):
    async def embed(self, req: EmbeddingRequest) -> EmbeddingResponse: ...
    @property
    def dim(self) -> int: ...

class Reranker(Protocol):
    async def rerank(self, req: RerankRequest) -> RerankResponse: ...

class OCR(Protocol):
    async def recognize(self, req: OCRRequest) -> OCRResult: ...
```

The dev sandbox uses `MockBackend` (recorded fixtures, zero ML deps, runs on
CPU). GPU tiers select real adapters by editing YAML — no code changes.

## 3. RAG pipeline (9-stage, the only entry point)

Naive `query → vector search → LLM` is forbidden. The pipeline is:

```
query → understand → rewrite/expand → hybrid retrieve → metadata filter
      → rerank → evidence select → LLM reason → evidence verify → respond
```

Each stage is a typed node. A query that fails evidence verification returns
`"I don't have sufficient evidence to answer this."` — this is a first-class
`Verdict`, not an error.

## 4. Agent orchestration

LangGraph `StateGraph` with a `Supervisor` node that classifies intent and
routes to sub-agents. Each sub-agent is a subgraph. State is checkpointed
(Postgres-backed checkpointer) so long ingestion/analysis workflows resume
after crash. HITL is a LangGraph `interrupt` — the workflow pauses, emits
an approval record, and resumes on human decision.

Agents:
- **Supervisor** — intent classification, task decomposition, routing
- **Document Intelligence** — parsing, OCR, classification, table extraction
- **Vision** — image understanding, diagrams, engineering drawings
- **Knowledge/RAG** — retrieval, evidence selection, grounded reasoning
- **Research** — optional external research; egress-gated; never sees KB
- **Evidence Verification** — verifies claims, detects contradictions
- **Risk/Decision** — findings, severity, recommended actions
- **Deliverable** — reports, summaries, action lists

## 5. Evidence & provenance

Every non-trivial claim is traceable to evidence:

```python
class Claim(BaseModel):
    text: str
    evidence: list[EvidenceRef]  # doc_id, page, section, chunk_id, span
    support_status: Literal["SUPPORTED","PARTIALLY_SUPPORTED","UNSUPPORTED","CONFLICTING"]
```

Reports render `support_status` per claim. Citations are structured, not free
text — the deliverable templates consume typed `Claim` objects.

## 6. Security posture

- Retrieved/extracted document text is **always** `tool`/`user` role — never
  `system`. See ADR 0003.
- Tool execution is sandboxed (subprocess + allow-list per agent).
- Egress gateway is the *only* outbound HTTP path; off by default; Research
  Agent is the only opt-in path and has no KB access.
- Postgres RLS on `project_id`; Qdrant queries carry a mandatory
  `project_id` filter.
- Audit log is append-only and hash-chained.

See `SECURITY.md` for the full controls matrix.

## 7. Storage

- **PostgreSQL** — metadata, audit, approvals, workflow state, RLS (Phase 11)
- **Qdrant** — vectors (embedded mode in dev, server mode in prod)
- **Object store** — document blobs (filesystem in dev, encrypted in prod)

SQLite is used in the dev sandbox for the relational DB to avoid a service
dependency. The schema targets Postgres features (RLS) which are added in
Phase 11.

## 8. Phase 1 contract surface

Phase 1 ships the *interfaces* every later phase depends on:

- `sovereign.core` — config, structured logging with redaction, ULID IDs,
  typed error hierarchy, OTEL telemetry stubs
- `sovereign.models` — 5 protocol interfaces, `ModelGateway` factory,
  `MockBackend` reference implementation, backend registry
- `sovereign.storage.db` — SQLAlchemy 2.0 models (`Project`, `User`,
  `Document`, `AuditEvent`), Alembic baseline migration
- `sovereign.audit` — append-only hash-chained audit log
- `sovereign.api` — FastAPI app with `/healthz`, `/readyz`, request ID
  middleware, structured logging middleware, typed exception handlers

Phase 1 explicitly does NOT include: ingestion, parsing, OCR, embeddings,
RAG, agents, frontend, real model adapters. Those land in Phases 2–14.

## 9. ADRs

Architectural decisions are recorded in `adrs/`:

- [0001 — Record architecture decisions](adrs/0001-record-architecture-decisions.md)
- [0002 — Model Gateway abstraction](adrs/0002-model-gateway-abstraction.md)
- [0003 — Retrieved documents are data, not instructions](adrs/0003-retrieved-doc-as-data-not-instruction.md)
