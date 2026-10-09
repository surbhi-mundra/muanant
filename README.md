# SOVEREIGN

**On-Premise Agentic AI Workbench Using Open-Weight Multimodal LLMs for Confidential Industrial Work.**

SOVEREIGN is a secure, on-premise, multimodal, agentic AI workbench for
organizations that cannot send confidential industrial information to
external cloud AI services. It supports document upload, OCR, multimodal
processing, organization-specific knowledge bases, grounded RAG, specialized
AI agents, evidence verification, risk/finding analysis, deliverable
generation, and audit trails — all inside the organization's controlled
environment.

> **Status:** All 14 phases complete. 411 tests passing.

---

## Table of Contents

- [Why SOVEREIGN?](#why-sovereign)
- [Architecture Overview](#architecture-overview)
- [Key Features (All 14 Phases)](#key-features-all-14-phases)
- [Quickstart](#quickstart)
- [Repository Structure](#repository-structure)
- [Configuration](#configuration)
- [Model Agnosticism](#model-agnosticism)
- [Security Posture](#security-posture)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Deployment](#deployment)
- [Development Roadmap (Completed)](#development-roadmap-completed)
- [License](#license)

---

## Why SOVEREIGN?

Industrial organizations — energy, manufacturing, infrastructure, defense,
pharma — handle confidential documents (inspection reports, engineering
drawings, incident records, IP-laden specifications) that *cannot* be sent
to cloud AI services. At the same time they need exactly what cloud AI
offers: document understanding, grounded Q&A, agentic workflows, risk
analysis, and automated report generation.

SOVEREIGN closes that gap by running an entire agentic AI workbench
on-premise, using open-weight multimodal models behind a model-agnostic
gateway. No cloud API calls. No data leaving the perimeter. No vendor
lock-in.

### Core Principles

1. **On-premise by design** — no cloud APIs in the confidential execution path
2. **Model-agnostic** — swap any LLM/VLM/embedding/reranker/OCR via YAML config
3. **Grounded by default** — "I don't have sufficient evidence" is a first-class response, not an error
4. **Evidence-traceable** — every claim links to (document, page, section, chunk)
5. **Security-first** — egress off by default, retrieved-doc-as-data (never system role), hash-chained audit

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  WORKBENCH (Next.js)  — upload, chat, citations, agents, approvals   │
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

The **ModelGateway** is the architectural keystone: every agent and
capability depends only on the protocol interfaces (`TextLLM`, `VisionLLM`,
`EmbeddingModel`, `Reranker`, `OCR`), never on a concrete adapter. Backends
are wired in `configs/models.yaml` and swapped without code changes.

---

## Key Features (All 14 Phases)

### Phase 1 — Repository + Architecture Foundation
- ModelGateway with 5 Protocol interfaces (TextLLM, VisionLLM, EmbeddingModel, Reranker, OCR)
- MockBackend for CPU-only dev (zero ML deps)
- Hash-chained append-only audit log
- FastAPI with health/readiness endpoints, structured logging, request ID middleware
- 3 ADRs documenting architectural decisions

### Phase 2 — Document Ingestion
- 6 structure-preserving parsers: PDF (PyMuPDF), DOCX (python-docx), TXT (chardet), Markdown, CSV, XLSX (openpyxl)
- Secure object store with opaque UUID keys, project-scoped paths, path traversal rejection
- Ingestion pipeline: validate → dedup (SHA-256) → store → parse → audit
- Structure-aware chunker with provenance (page, section_path, chunk_index)

### Phase 3 — OCR + Multimodal Processing
- Real Tesseract OCR adapter (satisfies the OCR protocol)
- Scanned-PDF detection (per-page text density analysis)
- OCR pipeline: detect → render → OCR → merge into ParsedDocument
- Auto-OCR of scanned PDFs and standalone images during ingestion
- Vision service with 4 specialized methods (general, diagram, inspection, text extraction)

### Phase 4 — Knowledge Base
- EmbeddingService via the EmbeddingModel protocol (MockBackend in dev)
- Qdrant vector store with project-scoped collections (embedded mode for dev)
- BM25 keyword index with stopword removal and standard ranking
- Hybrid retriever combining vector + keyword search via Reciprocal Rank Fusion (RRF)
- Auto-indexing on document upload, auto-removal on delete

### Phase 5 — Hybrid RAG (9-Stage Pipeline)
The sole entry point for grounded Q&A. Naive `query → vector search → LLM` is forbidden.

```
query → understand → rewrite → retrieve → filter → rerank
      → select → reason → verify → respond
```

- Stage 1: Query understanding (intent classification, key term extraction)
- Stage 2: Query rewriting/expansion (multi-query retrieval)
- Stage 3-4: Hybrid retrieval + metadata filtering
- Stage 5: Cross-encoder reranking
- Stage 6: Evidence selection with diversity cap
- Stage 7: LLM reasoning (evidence as `tool` role, never `system` — per ADR 0003)
- Stage 8: Evidence verification (SUPPORTED/PARTIALLY_SUPPORTED/UNSUPPORTED/CONFLICTING)
- Stage 9: Final response with first-class "insufficient evidence" verdict

### Phase 6 — Evidence & Citations
- Citation model with full provenance (document_id, page, section_path, chunk_id, evidence_text)
- EvidenceCollector with deduplication and source diversity
- ContradictionDetector (value mismatch + contradictory facts detection)
- CitationRenderer: 4 formats (markdown, inline, structured JSON, numbered list)
- EvidenceReport integrated into every RAG response

### Phase 7 — Agent Orchestration
- LangGraph supervisor-based architecture
- 7 sub-agents: RAG, DocIntel, Vision, Research, EvidenceVerify, Risk, Deliverable
- Typed AgentState shared across the graph
- Error-non-fatal execution (failures logged, graph continues)
- Each agent has a default sequence; supervisor classifies and routes

### Phase 8 — Vision Workflows
- DiagramExtractor: extracts figures from ParsedDocuments, renders PDF regions
- DrawingAnalyzer: specialized prompts for P&ID, electrical, mechanical, flowchart, photo
- ImageGroundedClaimer: extracts factual claims from diagram descriptions
- Full vision workflow: extract → describe → claim → summarize

### Phase 9 — Risk/Finding Analysis
- 5-level severity taxonomy: CRITICAL (100), HIGH (75), MEDIUM (50), LOW (25), INFO (10)
- RiskScorer: weighted-max + multi-finding bonus, overall risk score 0-100
- RiskAssessor: keyword-based finding extraction from answer + evidence
- Flags unsupported claims as MEDIUM, conflicting claims as HIGH
- Severity-specific recommended actions per finding
- RiskReport with summary, recommendations, findings by severity

### Phase 10 — Deliverable Generation
- 8 deliverable types: inspection, maintenance, incident, executive summary, action list, risk assessment, summary, custom
- DeliverableBuilder: assembles sections from agent outputs
- DeliverableRenderer: markdown, HTML, structured JSON
- DeliverableExporter: **7 formats** — JSON, markdown, HTML, CSV, XLSX, DOCX, PDF
- All deliverables preserve citation references

### Phase 11 — Security + Audit
- **AuthService**: local auth with PBKDF2 password hashing + JWT tokens
- **RBACService**: 3 roles (admin, analyst, viewer), 13 permissions, project isolation
- **EgressGateway**: controlled outbound HTTP (off by default, YAML allow-list)
- **Sandbox**: subprocess tool execution with timeout + output limits
- **InjectionGuard**: canary tokens, injection pattern detection, tool-role message builder
- **ApprovalQueue**: HITL approval workflow (submit, approve, reject, modify)

### Phase 12 — Frontend Workbench
- Next.js 16 workbench with 7 pages:
  - **Dashboard**: system status, KB stats, quick actions
  - **Documents**: upload, list, delete
  - **Search**: hybrid retrieval with provenance display
  - **RAG**: ask questions with verdict/claims/evidence
  - **Agents**: orchestration with task type, steps, findings, deliverable
  - **Deliverables**: generate + export to PDF/DOCX/XLSX/CSV/JSON/MD
  - **Audit**: chain verification info
- API client library with proxy config
- Tailwind CSS styling with severity badges

### Phase 13 — Evaluation
- RetrievalEvaluator: recall@k, precision@k, MRR
- RAGFaithfulnessEvaluator: checks answered→evidence, insufficient→no long answer, all-unsupported→fail
- InjectionTestSuite: 6 test cases (canary leakage, instruction override, role hijack, prompt extraction, normal, forget)
- RegressionCorpus: test queries with expected behavior
- `make eval` target for running the full suite

### Phase 14 — Deployment
- Dockerfiles for API (Python 3.12 slim + tesseract + qpdf) and Workbench (Next.js multi-stage)
- docker-compose for Tier 2 (api + workbench + postgres + qdrant)
- docker-compose.dev for Tier 1 (SQLite + embedded Qdrant)
- Kubernetes manifests for Tier 3 (StatefulSets, Deployments, Ingress with TLS)
- Comprehensive deployment guide (docs/deployment.md) covering Tier 1-4

---

## Quickstart

### Prerequisites
- Python ≥ 3.11
- [`uv`](https://github.com/astral-sh/uv) (recommended) or `pip`
- Tesseract OCR (`apt install tesseract-ocr` on Linux)
- qpdf (`apt install qpdf`)
- ~500 MB disk for deps
- No GPU required for dev (uses `MockBackend`)

### Install & Run

```bash
# 1. Install runtime + dev deps
make install

# 2. Apply DB migrations (or dev auto-creates schema)
make migrate

# 3. Run the API
make run

# 4. Health check
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
```

### Run Tests

```bash
make test          # full suite (411 tests)
make unit          # unit only
make integration   # integration only
make lint          # ruff check
make typecheck     # mypy strict
make eval          # evaluation suite
make audit         # pip-audit security scan
```

### Workbench (Frontend)

```bash
cd workbench
npm install
npm run dev        # http://127.0.0.1:3000
```

---

## Repository Structure

```
sovereign/
├── sovereign/                    # main Python package (96 files)
│   ├── core/                     # config, logging, ids, errors, telemetry
│   ├── models/                   # ModelGateway: 5 protocols + adapters
│   │   ├── schemas.py            # TextLLM, VisionLLM, EmbeddingModel, Reranker, OCR
│   │   ├── gateway.py            # ModelGateway factory
│   │   └── backends/
│   │       ├── mock.py           # MockBackend (CPU-only dev)
│   │       └── __init__.py       # backend registry
│   ├── storage/
│   │   ├── db/                   # SQLAlchemy 2.0 models + Alembic
│   │   ├── qdrant.py             # Qdrant vector store
│   │   └── objects.py            # object store (filesystem/S3)
│   ├── ingestion/                # secure upload, quarantine, validation
│   ├── parsing/                  # 6 parsers + chunker
│   ├── ocr/                      # Tesseract adapter + OCR pipeline
│   ├── vision/                   # vision service + workflows
│   ├── embeddings/               # embedding service + indexing
│   ├── retrieval/                # hybrid retrieval + RRF fusion + BM25
│   ├── reranking/                # cross-encoder reranker
│   ├── rag/                      # 9-stage RAG pipeline
│   ├── evidence/                 # citations, collector, contradictions, renderer
│   ├── agents/                   # supervisor + 7 sub-agents
│   ├── orchestration/            # LangGraph graph
│   ├── risk/                     # findings, severity, scoring
│   ├── deliverables/             # builder, renderer, exporter (7 formats)
│   ├── security/                 # auth, RBAC, egress, sandbox, injection, approvals
│   ├── audit/                    # hash-chained audit log
│   ├── evaluation/               # retrieval, faithfulness, injection tests
│   └── api/
│       ├── app.py                # FastAPI app
│       ├── middleware.py         # request ID, logging, error handlers
│       └── routes/               # 7 route modules
│           ├── health.py
│           ├── documents.py
│           ├── vision_ocr.py
│           ├── knowledge_base.py
│           ├── rag.py
│           ├── agents.py
│           └── deliverables.py
├── workbench/                    # Next.js 16 frontend (7 pages)
├── tests/                        # 31 test files, 411 tests
├── alembic/                      # DB migrations
├── configs/                      # YAML configs (models, dev, prod, policies)
├── scripts/                      # ops scripts (verify_audit_chain.py)
├── infra/                        # deployment
│   ├── docker/                   # Dockerfiles
│   ├── compose/                  # docker-compose (dev + prod)
│   └── k8s/                      # Kubernetes manifests
├── adrs/                         # 3 architecture decision records
├── docs/                         # architecture, security, deployment, hardware, models
├── pyproject.toml                # dependencies + tooling config
├── Makefile                      # install, dev, test, lint, migrate, eval, audit
├── README.md                     # this file
├── ARCHITECTURE.md               # full architecture doc
└── SECURITY.md                   # threat model + controls matrix
```

---

## Configuration

### Environment Variables (`.env`)

| Variable | Default | Description |
|---|---|---|
| `SOVEREIGN_ENV` | `dev` | Environment: dev, staging, prod |
| `DATABASE_URL` | `sqlite:///./sovereign.db` | Database connection string |
| `QDRANT_URL` | (empty) | Qdrant URL (empty = embedded mode) |
| `OBJECT_STORE_FS_ROOT` | `./storage/objects` | Object store root directory |
| `EGRESS_ENABLED` | `false` | Enable outbound HTTP (off by default) |
| `SOVEREIGN_JWT_SECRET` | `dev-only-not-for-prod` | JWT signing secret |
| `MODEL_GATEWAY_CONFIG` | `configs/models.yaml` | Model backend config path |

### Config Files

| File | Purpose |
|---|---|
| `configs/models.yaml` | ModelGateway backend wiring (mock → real swap) |
| `configs/dev.yaml` | Dev environment defaults |
| `configs/prod.yaml` | Prod environment defaults |
| `configs/policies.yaml` | Egress allow-list, tool allow-lists, ingestion limits |

### Switching to Real Models

Edit `configs/models.yaml` to swap from mock to real backends:

```yaml
text:
  backend: vllm.text
  model_name: Qwen/Qwen2.5-7B-Instruct
  server_url: http://127.0.0.1:8001
  quantization: awq

vision:
  backend: vllm.vision
  model_name: Qwen/Qwen2-VL-7B-Instruct
  server_url: http://127.0.0.1:8002

embedding:
  backend: sentence_transformers.embedding
  model_name: BAAI/bge-m3
  dim: 1024

reranker:
  backend: cross_encoder.reranker
  model_name: BAAI/bge-reranker-v2-m3

ocr:
  backend: tesseract.ocr
  model_name: tesseract-5.x
```

---

## Model Agnosticism

The **ModelGateway** is the architectural guarantee that makes SOVEREIGN
model-agnostic. Every agent and capability depends only on the Protocol
interfaces, never on a concrete adapter.

```python
# sovereign/models/schemas.py
class TextLLM(Protocol):
    async def complete(self, req: LLMRequest) -> LLMResponse: ...

class VisionLLM(Protocol):
    async def describe(self, req: VisionRequest) -> VisionResponse: ...

class EmbeddingModel(Protocol):
    async def embed(self, req: EmbeddingRequest) -> EmbeddingResponse: ...

class Reranker(Protocol):
    async def rerank(self, req: RerankRequest) -> RerankResponse: ...

class OCR(Protocol):
    async def recognize(self, req: OCRRequest) -> OCRResult: ...
```

**The development model used to build SOVEREIGN has no special status
inside the system.** Any open-weight model that satisfies the protocol
interface can be used — the swap is a YAML edit, not a code change.

See [ADR 0002](adrs/0002-model-gateway-abstraction.md) for the full rationale.

### Recommended Models by Tier

| Tier | Hardware | Text LLM | Vision LLM | Embedding | Reranker |
|---|---|---|---|---|---|
| 1 (dev) | CPU, no GPU | MockBackend | MockBackend | MockBackend | MockBackend |
| 2 (1 GPU) | 24GB VRAM | Qwen2.5-7B (AWQ) | Qwen2-VL-7B (AWQ) | bge-m3 | bge-reranker-v2-m3 |
| 3 (2-4 GPU) | 80GB VRAM each | Qwen2.5-32B (AWQ) | Qwen2-VL-72B (AWQ) | bge-m3 | bge-reranker-v2-m3 |
| 4 (8+ GPU) | 8× H100 | Qwen2.5-72B (TP) | Qwen2-VL-72B (TP) | bge-m3 (TEI) | bge-reranker-v2-m3 (TEI) |

See [docs/hardware-tiers.md](docs/hardware-tiers.md) and
[docs/model-catalog.md](docs/model-catalog.md) for details.

---

## Security Posture

SOVEREIGN is designed for confidential industrial work. Key guarantees:

- **Off-by-default egress.** No outbound network calls unless explicitly
  enabled per request. The Research Agent is the *only* opt-in egress path.
- **Retrieved-doc-as-data, not instruction.** Every chunk retrieved from
  the KB is injected into LLM context as `tool` role, never `system`.
  See [ADR 0003](adrs/0003-retrieved-doc-as-data-not-instruction.md).
- **Append-only hash-chained audit log.** Every meaningful action is
  recorded; tampering breaks the chain. See `scripts/verify_audit_chain.py`.
- **Project isolation.** Every query carries a `project_id` filter at the
  DB and vector-store level.
- **No model lock-in.** The ModelGateway guarantees that swapping the
  underlying model is a config change, not a code change.
- **Prompt injection defense.** Canary tokens, output validators, per-agent
  tool allow-lists, sandboxed tool execution.
- **RBAC + HITL.** 3 roles (admin, analyst, viewer), human approval required
  for high-impact actions.

See [`SECURITY.md`](SECURITY.md) for the full controls matrix.

---

## API Reference

### Health
| Method | Path | Description |
|---|---|---|
| GET | `/healthz` | Liveness probe |
| GET | `/readyz` | Readiness probe (DB + ModelGateway + audit) |

### Documents
| Method | Path | Description |
|---|---|---|
| POST | `/documents` | Upload document (multipart) |
| GET | `/documents` | List documents |
| GET | `/documents/{id}` | Get document metadata |
| GET | `/documents/{id}/parsed` | Get parsed structure |
| DELETE | `/documents/{id}` | Delete document |
| POST | `/documents/{id}/index` | Re-index document |
| DELETE | `/documents/{id}/index` | Remove from index |
| POST | `/documents/{id}/re-ocr` | Re-run OCR |

### Knowledge Base
| Method | Path | Description |
|---|---|---|
| POST | `/search` | Hybrid retrieval search |
| GET | `/kb/stats` | KB statistics |

### RAG
| Method | Path | Description |
|---|---|---|
| POST | `/rag/query` | Ask a grounded question |
| POST | `/rag/query/markdown` | Same, returns markdown |

### Agents
| Method | Path | Description |
|---|---|---|
| POST | `/agents/query` | Run agent orchestration |

### Deliverables
| Method | Path | Description |
|---|---|---|
| POST | `/deliverables` | Generate deliverable |
| POST | `/deliverables/export?format=` | Export (pdf, docx, xlsx, csv, json, md, html) |

### Vision & OCR
| Method | Path | Description |
|---|---|---|
| POST | `/vision/describe` | Describe an image |
| POST | `/vision/diagram` | Describe an engineering diagram |
| POST | `/vision/inspect` | Describe an inspection photo |
| POST | `/ocr/image` | OCR a standalone image |

---

## Testing

```bash
make test          # 411 tests
make unit          # unit tests only
make integration   # integration tests only
make lint          # ruff check
make typecheck     # mypy strict (96 files)
make eval          # evaluation suite (retrieval, faithfulness, injection)
```

### Test Coverage by Phase

| Phase | Tests | What's Tested |
|---|---|---|
| 1 | 58 | config, logging, IDs, audit chain, model gateway, API health |
| 2 | 74 | parsers, chunker, object store, ingestion integration |
| 3 | 32 | Tesseract OCR, scanned detection, pipeline, vision service |
| 4 | 40 | embeddings, Qdrant, BM25, hybrid retrieval, indexing |
| 5 | 37 | 9-stage RAG pipeline, evidence verification |
| 6 | 31 | citations, collector, contradictions, renderer |
| 7 | 31 | supervisor routing, 7 sub-agents, orchestrator |
| 8 | 20 | diagram extraction, drawing analysis, image-grounded claims |
| 9 | 19 | findings, severity scoring, risk assessor |
| 10 | 20 | deliverable builder, renderer, 7 export formats |
| 11 | 35 | auth, RBAC, egress, sandbox, injection guard, approvals |
| 13 | 14 | retrieval eval, faithfulness, injection test suite |
| **Total** | **411** | |

---

## Deployment

### Tier 1: Developer Machine (dev)

```bash
make install
make migrate
make run
```

### Tier 2: Single GPU Workstation (Docker Compose)

```bash
export SOVEREIGN_JWT_SECRET=$(openssl rand -hex 32)
docker compose -f infra/compose/docker-compose.yml up -d
```

### Tier 3: Enterprise GPU Server (Kubernetes)

```bash
kubectl create namespace sovereign
kubectl create secret generic sovereign-api-secret \
  --from-literal=jwt-secret=$(openssl rand -hex 32) -n sovereign
kubectl apply -f infra/k8s/deployment.yaml
```

See [docs/deployment.md](docs/deployment.md) for the full deployment guide
covering all 4 tiers, model configuration, vLLM setup, security checklist,
backup, and monitoring.

---

## Development Roadmap (Completed)

| Phase | Status | Deliverable |
|---|---|---|
| 1 | ✅ | Repository + architecture foundation |
| 2 | ✅ | Document ingestion |
| 3 | ✅ | OCR + multimodal processing |
| 4 | ✅ | Knowledge base |
| 5 | ✅ | Hybrid RAG (9-stage pipeline) |
| 6 | ✅ | Evidence/citations |
| 7 | ✅ | Agent orchestration |
| 8 | ✅ | Vision workflows |
| 9 | ✅ | Risk/finding analysis |
| 10 | ✅ | Deliverable generation |
| 11 | ✅ | Security + audit |
| 12 | ✅ | Frontend workbench |
| 13 | ✅ | Evaluation |
| 14 | ✅ | Deployment |

---

## License

Proprietary. All rights reserved.

---

## Acknowledgments

SOVEREIGN was built incrementally across 14 phases, with each phase
building on the contract surfaces established by the prior phases. The
architecture prioritizes:

1. **Interfaces before implementations** — every subsystem depends on
   protocols, not concrete adapters
2. **Provenance before convenience** — every claim traces to evidence
3. **Safety before capability** — "I don't know" is always acceptable;
   hallucination is never acceptable
4. **Configuration over code** — model swaps, policy changes, and
   environment tuning are YAML edits, not code changes

For architectural rationale, see the [ADRs](adrs/). For the full system
design, see [ARCHITECTURE.md](ARCHITECTURE.md). For security controls,
see [SECURITY.md](SECURITY.md).
