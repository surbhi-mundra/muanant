# SOVEREIGN — Multi-Agent Work Log

This file is the shared work log for all agents working on SOVEREIGN.
Each agent appends a new section (starting with `---`) after completing its
task. Do NOT overwrite existing content.

---
Task ID: phase-1
Agent: Principal Engineer (main)
Task: Phase 1 — Repository + architecture foundation. Build the contract surface that every later phase depends on, with zero business logic. Must run on CPU-only dev sandbox (2 vCPU, 4GB RAM, no GPU) using MockBackend.

Work Log:
- Inspected existing repository: greenfield (only .git initial commit, empty download/, .env with DATABASE_URL, .gitignore)
- Probed dev sandbox: Python 3.12, uv, pytest present; no GPU; pre-installed: fastapi, pymupdf, cv2, pandas, python-docx, reportlab; missing: sqlalchemy, alembic, qdrant-client, structlog, tenacity, pyjwt, passlib, ruff, mypy
- Produced 10-point architecture analysis (current state, missing functionality, tech debt, architecture/security risks, target architecture, repo structure, 14-phase roadmap, Phase 1 milestone, 10 architectural decisions)
- User approved all decisions (D1-D10): LangGraph, Qdrant, Postgres everywhere, Tesseract baseline, PyMuPDF+python-docx first, vLLM for prod, Next.js, OIDC+local auth, egress off by default, Phase 1 scope as proposed
- Created monorepo directory structure (sovereign/ package + 18 subpackages, workbench/, tests/, alembic/, configs/, scripts/, infra/, adrs/, docs/)
- Wrote pyproject.toml with uv workspace, pinned runtime deps (fastapi, sqlalchemy>=2, alembic, qdrant-client, structlog, tenacity, pyjwt, passlib[argon2], pydantic-settings) and dev deps (pytest, ruff, mypy, pip-audit). Heavy ML deps (torch, transformers, vllm) in optional extras only — NOT installed in dev.
- Wrote tooling: ruff.toml (strict, with bandit), mypy.ini (strict), pytest.ini (asyncio_mode=auto, requires_gpu marker), .pre-commit-config.yaml, Makefile (install/dev/run/test/lint/typecheck/migrate/audit)
- Implemented sovereign/core/: config.py (pydantic-settings with YAML+env+dotenv source priority via settings_customise_sources, AliasChoices for SOVEREIGN_ENV→env field), logging.py (structlog JSON + redactor processor that scrubs known-secret keys and patterns), ids.py (ULID generation, monotonic within ms), errors.py (typed hierarchy with stable codes + http_status), telemetry.py (OTEL stubs)
- Implemented sovereign/models/: schemas.py (5 Protocol interfaces: TextLLM, VisionLLM, EmbeddingModel, Reranker, OCR + request/response dataclasses), backends/mock.py (MockBackend — CPU-only reference implementation with deterministic hash-based embeddings, lexical-overlap reranker, placeholder OCR/vision), backends/__init__.py (backend registry with register_backend/get_backend), gateway.py (ModelGateway factory reading configs/models.yaml, lazy backend construction, runtime Protocol compliance check)
- Implemented sovereign/storage/db/: base.py (SQLAlchemy 2.0 declarative base, engine factory with StaticPool for SQLite :memory:, session_scope context manager, init_schema with drop_all+create_all for test isolation), models.py (Project, User, Document stub, AuditEvent with hash-chain fields), alembic/env.py + versions/0001_baseline.py (baseline migration creating all 4 tables)
- Implemented sovereign/audit/: chain.py (AuditEventPayload dataclass with canonical_json for deterministic hashing, compute_hash, verify_chain with constant-time comparison), log.py (write_event with atomic sequence allocation + hash computation, read_chain, verify_full_chain, _payload_from_row for round-trip verification)
- Implemented sovereign/api/: app.py (FastAPI app with lifespan that configures logging, inits schema in dev, pre-constructs ModelGateway, includes health router), middleware.py (RequestContextMiddleware for X-Request-ID, LoggingMiddleware for structured request logging, sovereign_exception_handler translating SovereignError→JSON, unhandled_exception_handler for last-resort 500), deps.py (DI for Settings, Session, ModelGateway), routes/health.py (/healthz liveness, /readyz readiness checking DB+ModelGateway+audit)
- Implemented sovereign/cli/__main__.py (admin CLI skeleton with version + audit-verify subcommands)
- Wrote configs/: models.yaml (all 5 capabilities → mock.* backends, with commented-out real backend examples for vLLM/sentence-transformers/tesseract/surya), dev.yaml (dev defaults), prod.yaml (prod defaults with Postgres+Qdrant server), policies.yaml (egress allowlist empty+disabled, per-agent tool allowlists, ingestion limits, prompt_injection config with canary tokens)
- Wrote scripts/verify_audit_chain.py (standalone CLI to verify audit log integrity, designed for cron in prod)
- Wrote tests/: conftest.py (sys.path setup, default :memory: SQLite), unit/test_config.py (8 tests: defaults, env overrides, YAML priority, AliasChoices, caching), unit/test_logging.py (5 tests: redactor scrubs keys/nested-dicts/postgres-URLs/bearer-tokens, end-to-end log redaction), unit/test_ids.py (8 tests: ULID format/uniqueness/sortability, token/request/workflow ID formats, tz-aware utcnow), unit/test_audit_chain.py (10 tests: hash determinism, genesis hash, chain linking, full chain verification, tamper detection, ordered reads, canonical JSON stability, None dropping), unit/test_model_gateway.py (20 tests: backend registry, Protocol compliance for all 5 mocks, functional tests for each mock, gateway lazy construction, gateway describe, unknown backend rejection), integration/test_api_health.py (6 tests: root, healthz, readyz, request-ID header, client-supplied request-ID echo, OpenAPI spec), integration/test_gateway_mock.py (1 smoke test: full gateway round-trip + audit chain write + verify)
- Wrote docs/: README.md (quickstart, repo layout, roadmap, security posture), ARCHITECTURE.md (layered design, ModelGateway, 9-stage RAG, agent orchestration, evidence model, security posture, Phase 1 contract surface), SECURITY.md (threat model, 12-control matrix, 6 critical invariants), docs/hardware-tiers.md (Tier 1-4 with VRAM/quant/context/license per model), docs/model-catalog.md (recommended models per capability with license compliance checklist)
- Wrote 3 ADRs: 0001 (record architecture decisions — why ADRs over inline comments/wiki), 0002 (ModelGateway abstraction — why Protocol interfaces over direct calls/LangChain), 0003 (retrieved docs are data not instructions — why tool role over system role + defense-in-depth with canaries/validators/allow-lists/sandbox/egress-off)
- Installed deps via uv pip install -e ".[dev]" (all deps installed successfully, no ML deps needed)
- Fixed 3 bugs during testing: (1) duplicate index declaration in Document model (index=True + explicit Index in __table_args__), (2) test isolation failure due to cached Settings not picking up per-test DATABASE_URL changes — fixed with reset_settings_cache() in fixtures + StaticPool for :memory: SQLite, (3) config source priority wrong — model_copy(updates=yaml) was overriding env vars — fixed with settings_customise_sources putting env > dotenv > yaml > init, (4) SOVEREIGN_ENV not mapping to env field — fixed with AliasChoices("SOVEREIGN_ENV", "ENV", "env")
- Fixed lint issues: moved lazy imports to top-level, added # noqa for intentional lazy imports (circular dep avoidance, CLI startup speed), configured per-file-ignores for tests (S101, S105, S106, PLR2004)
- Fixed mypy issues: cast json.loads return to dict[str, Any], remove unnecessary metadata override on Base, explicit type annotation for structlog.get_logger return, fix verify_chain signature (sequence is int not str), widen exception handler signature to Exception for Starlette compatibility
- Verified: ruff check clean (0 errors), mypy strict clean (0 errors in 27 files), 58/58 tests pass in 2.2s, Alembic baseline migration creates all 4 tables, API boots and serves /healthz (200), /readyz (200 with all checks ok), / (200), /openapi.json (200 with 3 paths)

Stage Summary:
- Phase 1 COMPLETE. The contract surface for all 14 phases is in place.
- 5 Protocol interfaces (TextLLM, VisionLLM, EmbeddingModel, Reranker, OCR) + ModelGateway factory guarantee model-agnosticism — swapping any model is a YAML edit, not a code change.
- MockBackend runs the entire pipeline on CPU with zero ML deps — dev sandbox and CI use it; GPU tiers swap to real backends via configs/models.yaml.
- Hash-chained audit log is functional and tested (including tamper detection).
- All 10 architectural decisions (D1-D10) are implemented or have their contract surface ready: LangGraph (Phase 7), Qdrant (Phase 4), Postgres schema (baseline migration ready, RLS in Phase 11), Tesseract (Phase 3, via OCR protocol), vLLM (Phase 14, via TextLLM protocol), Next.js (Phase 12), OIDC+local auth (Phase 11), egress off by default (enforced in config + policies.yaml).
- 3 ADRs document the architectural rationale (model gateway, retrieved-doc-as-data, ADR process itself).
- Ready for Phase 2 (Document ingestion) upon user approval.

Artifacts produced:
- 40+ Python source files in sovereign/ package
- 8 test files (58 tests, all passing)
- 4 YAML config files (models, dev, prod, policies)
- 1 Alembic baseline migration
- 6 documentation files (README, ARCHITECTURE, SECURITY, hardware-tiers, model-catalog, ADRs README)
- 3 ADRs (0001, 0002, 0003)
- Makefile, pyproject.toml, ruff/mypy/pytest configs, .pre-commit-config.yaml, .env.example, .gitignore
- scripts/verify_audit_chain.py (audit integrity CLI)
