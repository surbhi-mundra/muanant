# SOVEREIGN

**On-Premise Agentic AI Workbench Using Open-Weight Multimodal LLMs for Confidential Industrial Work.**

SOVEREIGN is a secure, on-premise, multimodal, agentic AI workbench for
organizations that cannot send confidential industrial information to
external cloud AI services. It supports document upload, OCR, multimodal
processing, organization-specific knowledge bases, grounded RAG, specialized
AI agents, evidence verification, risk/finding analysis, deliverable
generation, and audit trails — all inside the organization's controlled
environment.

> **Status:** Phase 1 (foundation) complete. See [Development Roadmap](#development-roadmap).

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

---

## Architecture (Phase 1 surface)

```
Workbench (Next.js, Phase 12) → API (FastAPI) → Capabilities → ModelGateway → Backends
                                                          ↕
                                              Storage (SQLAlchemy, Qdrant, Object Store)
                              Cross-cutting: security | audit | observability | config
```

The **ModelGateway** is the architectural keystone: every agent and
capability depends only on the protocol interfaces (`TextLLM`, `VisionLLM`,
`EmbeddingModel`, `Reranker`, `OCR`), never on a concrete adapter. Backends
are wired in `configs/models.yaml` and swapped without code changes.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full layered design and
[`docs/hardware-tiers.md`](docs/hardware-tiers.md) for deployment profiles.

---

## Quickstart (dev)

### Prerequisites
- Python ≥ 3.11
- [`uv`](https://github.com/astral-sh/uv) (recommended) or `pip`
- ~500 MB disk for deps
- No GPU required for Phase 1 (uses `MockBackend`)

### Install & run

```bash
# 1. Install runtime + dev deps
make install

# 2. Apply DB migrations (or `make` auto-creates schema in dev)
make migrate

# 3. Run the API
make run

# 4. Health check
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
```

### Run tests

```bash
make test          # full suite
make unit          # unit only
make integration   # integration only
make lint          # ruff
make typecheck     # mypy strict
make audit         # pip-audit
```

### Configuration

- `.env` — runtime env (copy from `.env.example`)
- `configs/dev.yaml` — dev defaults
- `configs/prod.yaml` — prod defaults
- `configs/models.yaml` — ModelGateway backend wiring
- `configs/policies.yaml` — egress allowlist, tool allowlists, ingestion limits

To switch from the dev `MockBackend` to a real backend, edit
`configs/models.yaml` — no code changes. See [ADR 0002](adrs/0002-model-gateway-abstraction.md).

---

## Repository layout

```
sovereign/
├── sovereign/        # main Python package
│   ├── core/         # config, logging, ids, errors, telemetry
│   ├── models/       # ModelGateway: interfaces + adapters
│   ├── storage/      # SQLAlchemy + Alembic + Qdrant + object store
│   ├── ingestion/    # secure upload, quarantine, validation (Phase 2)
│   ├── parsing/      # structure-preserving parsers (Phase 2)
│   ├── ocr/          # OCR pipeline (Phase 3)
│   ├── vision/       # multimodal processing (Phase 8)
│   ├── embeddings/   # embed + index (Phase 4)
│   ├── retrieval/    # hybrid retrieval (Phase 5)
│   ├── reranking/    # reranker (Phase 5)
│   ├── rag/          # 9-stage grounded pipeline (Phase 5)
│   ├── evidence/     # claim/evidence model (Phase 6)
│   ├── agents/       # LangGraph supervisor + sub-agents (Phase 7)
│   ├── orchestration/ # graph wiring, checkpointer, HITL (Phase 7)
│   ├── risk/         # findings, severity (Phase 9)
│   ├── deliverables/ # report templates + exporters (Phase 10)
│   ├── approvals/    # HITL queue (Phase 11)
│   ├── security/     # egress, sandbox, RBAC (Phase 11)
│   ├── audit/        # hash-chained audit log
│   ├── api/          # FastAPI app + routes
│   └── cli/          # admin CLI
├── workbench/        # Next.js frontend (Phase 12)
├── tests/            # unit + integration
├── alembic/          # DB migrations
├── configs/          # YAML configs
├── scripts/          # ops scripts
├── infra/            # docker / compose / k8s / ansible
├── adrs/             # architecture decision records
└── docs/             # architecture / security / deployment docs
```

---

## Development roadmap

| Phase | Status | Deliverable |
|---|---|---|
| 1 | ✅ Done | Repo + architecture foundation (this phase) |
| 2 | ⏳ Next | Document ingestion |
| 3 | ⏳ | OCR + multimodal processing |
| 4 | ⏳ | Knowledge base |
| 5 | ⏳ | Hybrid RAG |
| 6 | ⏳ | Evidence/citations |
| 7 | ⏳ | Agent orchestration |
| 8 | ⏳ | Vision workflows |
| 9 | ⏳ | Risk/finding analysis |
| 10 | ⏳ | Deliverable generation |
| 11 | ⏳ | Security + audit |
| 12 | ⏳ | Frontend workbench |
| 13 | ⏳ | Evaluation |
| 14 | ⏳ | Deployment |

---

## Security posture

SOVEREIGN is designed for confidential industrial work. Key guarantees:

- **Off-by-default egress.** No outbound network calls unless explicitly
  enabled per request. The Research Agent is the *only* opt-in egress path.
- **Retrieved-doc-as-data, not instruction.** Every chunk retrieved from
  the KB is injected into LLM context as `tool`/`user` role, never `system`.
  See [ADR 0003](adrs/0003-retrieved-doc-as-data-not-instruction.md).
- **Append-only hash-chained audit log.** Every meaningful action is
  recorded; tampering breaks the chain. See `scripts/verify_audit_chain.py`.
- **Project isolation.** Every query carries a `project_id` filter at the
  DB and vector-store level. Postgres RLS adds defense-in-depth in Phase 11.
- **No model lock-in.** The ModelGateway guarantees that swapping the
  underlying LLM/embedding/reranker/OCR/vision model is a config change,
  not a code change. The dev model you're reading this from has no special
  status inside SOVEREIGN.

See [`SECURITY.md`](SECURITY.md) for the full controls matrix.

---

## License

Proprietary. All rights reserved.
