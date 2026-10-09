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

---
Task ID: phase-2
Agent: Principal Engineer (main)
Task: Phase 2 — Document ingestion. Build secure upload, validation, quarantine, structure-preserving parsers for PDF/DOCX/TXT/MD/CSV/XLSX, chunker with provenance, object store, and API routes.

Work Log:
- Recovered from session reset: storage/db/ files were lost between sessions (empty dirs not preserved). Recreated base.py, models.py, __init__.py from conversation context. Reinstalled deps via uv.
- Implemented sovereign/storage/objects.py: FilesystemObjectStore with opaque UUID keys, project-scoped paths (2-char sharding), path traversal rejection, atomic write (tmp+rename), Protocol interface for S3 swap-in later.
- Implemented sovereign/parsing/model.py: ParsedDocument (pydantic) with Page, Block (heading/paragraph/list_item/table/figure/caption/code/quote/page_break), Table (with TableRow/TableCell), Figure, BoundingBox, DocumentMetadata. Properties: all_blocks, total_text, headings, tables, figures.
- Implemented 6 parsers:
  - pdf.py (PyMuPDF/fitz): pages, font-size heading heuristic, text blocks with bounding boxes, image blocks as figures, metadata extraction.
  - docx.py (python-docx): heading levels from styles, paragraphs, list items, tables with markdown rendering, core properties metadata.
  - txt.py (chardet): encoding detection, paragraph splitting, ALL-CAPS heading detection, encoding in metadata.
  - markdown.py (lightweight regex): heading hierarchy with section_path, list items, code fences, tables (pipe syntax), blockquotes, paragraph accumulation.
  - csv.py (stdlib csv): delimiter detection (comma/semicolon/tab), header+rows as Table, markdown rendering.
  - xlsx.py (openpyxl): per-sheet table blocks, cell value conversion (int/float/bool/str), sheet names in section_path.
- Implemented sovereign/parsing/registry.py: MIME→parser dispatch, supported_mimes(), parse_document() entry point.
- Implemented sovereign/parsing/chunking.py: structure-aware Chunker with target/max/min word limits, overlap. Tables and figures as standalone chunks. Heading boundaries respected. Provenance (page, section_path, chunk_index) on every Chunk. Long text splitting with overlap.
- Implemented sovereign/ingestion/service.py: full ingestion pipeline:
  - _detect_mime: magic bytes detection (PDF, ZIP→DOCX/XLSX distinction, text), never trusts client Content-Type alone.
  - validate_document: size check, MIME detection, SHA-256, qpdf integrity check for PDFs.
  - ingest_document: validate → dedup (SHA-256) → store (opaque UUID key) → parse → persist Document row → store ParsedDocument JSON → audit event. Quarantine on validation failure. Versioning by filename.
  - get_document, get_parsed_document, list_documents, delete_document with project isolation.
- Implemented sovereign/api/routes/documents.py: POST /documents (multipart upload), GET /documents (list), GET /{id} (metadata), GET /{id}/parsed (ParsedDocument JSON), DELETE /{id}. Wired into app.py.
- Wrote 5 test files (74 new tests):
  - test_parsing.py: 25 tests across all 6 parsers (format, headings, paragraphs, tables, metadata, section paths, code blocks, blockquotes, cell values, page extraction, registry dispatch).
  - test_chunking.py: 8 tests (chunk production, heading boundaries, standalone tables, provenance, long text splitting, sequential indices, empty doc, section_label).
  - test_object_store.py: 12 tests (put/get, exists, idempotent delete, not found, project isolation, path traversal rejection, empty project/key rejection, stream, overwrite, key uniqueness, hex format).
  - test_ingestion.py: 21 integration tests (validation for all formats, magic byte detection, dedup, versioning, parse+store+retrieve, quarantine, list, delete, project isolation, audit trail).
  - test_documents_api.py: 8 API integration tests (upload, list, get by ID, get parsed, delete, 404 handling, duplicate, quarantine).
- Fixed bugs during testing: (1) TXT parser test expectation (Introduction not all-caps = paragraph, correct), (2) chunker long-text splitter using broken sentence-based approach — rewrote with simple word-count sliding window.
- Fixed lint: RUF012 (ClassVar for parser class attributes), PLC0415 (noqa for lazy imports in parsers/ingestion/tests), PLR0912/0915 (per-file-ignores for inherently branchy parser code), E501 (line length), E741 (ambiguous variable), RUF005 (list concatenation), unused type:ignore in docx imports.
- Fixed mypy: variable redefinition in pdf.py, None-attribute access in markdown.py table parser (rewrote messy function), optional access in chunking.py figure handling, removed unnecessary type:ignore from docx.py.

Stage Summary:
- Phase 2 COMPLETE. 132/132 tests pass (58 Phase 1 + 74 Phase 2). Ruff clean. Mypy clean (42 files).
- All 6 document formats (PDF, DOCX, TXT, MD, CSV, XLSX) parse to a unified ParsedDocument model preserving pages, headings, sections, tables, figures, metadata.
- Ingestion pipeline: upload → magic-byte MIME detection → SHA-256 dedup → opaque-key storage → structure-preserving parse → DB persist → audit event. Quarantine for invalid files.
- Object store enforces project isolation and rejects path traversal (security requirement S3).
- API endpoints: POST /documents, GET /documents, GET /{id}, GET /{id}/parsed, DELETE /{id}.
- Chunker produces provenance-carrying chunks ready for Phase 4 (embeddings + KB).
- Ready for Phase 3 (OCR + multimodal processing) upon user approval.

Artifacts produced:
- 15 new Python source files (parsing/model.py, base.py, pdf.py, docx.py, txt.py, markdown.py, csv.py, xlsx.py, registry.py, chunking.py; ingestion/service.py, __init__.py; storage/objects.py; api/routes/documents.py)
- 5 new test files (74 tests)
- Updated: sovereign/api/app.py (documents router), pyproject.toml (per-file-ignores)

---
Task ID: phase-3
Agent: Principal Engineer (main)
Task: Phase 3 — OCR + multimodal processing. Build real Tesseract OCR adapter, scanned-PDF detection, OCR pipeline, vision service, wire into ingestion for auto-OCR of scanned PDFs and images, and add API routes.

Work Log:
- Implemented sovereign/ocr/tesseract.py: TesseractOCR adapter satisfying the OCR protocol from Phase 1. Real OCR via pytesseract + tesseract 5.5.0 binary. Features: PIL Image loading from bytes/path, image preprocessing (grayscale, upscale, contrast, sharpen), simple text-only OCR, layout-mode OCR with blocks/lines/words + bounding boxes, confidence scoring, line grouping from tesseract word-level data, block grouping by vertical gap heuristic.
- Registered TesseractOCR in sovereign/models/backends/__init__.py as "tesseract.ocr" — eagerly imported because tesseract is CPU-only and always available. Added pytesseract + Pillow to core dependencies in pyproject.toml.
- Implemented sovereign/ocr/pipeline.py: OCR pipeline for PDFs and standalone images.
  - detect_scanned_pdf: per-page detection using text char count, image count, and text density. Handles text PDFs (not scanned), fully scanned PDFs, and mixed PDFs (some text + some scanned pages).
  - render_pdf_page_to_image: renders PDF page to PNG at configurable DPI via PyMuPDF.
  - ocr_pdf: main pipeline — detect scanned pages, render to image, OCR each, merge results into ParsedDocument. Text pages keep their original text; only scanned pages get OCR'd. Includes provenance metadata (OCR engine, scanned page count).
  - ocr_image: standalone image OCR — renders to ParsedDocument with single page.
  - OCROptions dataclass: render_dpi, languages, with_layout, min_confidence.
- Implemented sovereign/vision/service.py: VisionService using the VisionLLM protocol from ModelGateway. Methods: describe_image (general), describe_diagram (engineering schematics/P&IDs with specialized prompt), describe_inspection_image (industrial inspection photos), extract_text_from_image (vision-based OCR). Uses MockBackend in dev, real vision models in prod.
- Updated sovereign/ingestion/service.py: ingest_document is now async. Auto-detects scanned PDFs and runs OCR pipeline. Handles image MIME types (PNG/JPEG/WEBP) via ocr_image. Added image magic bytes to _MAGIC_BYTES (PNG, JPEG, WEBP/RIFF). Three code paths: images → ocr_image, PDFs → detect scanned → ocr_pdf or parse_document, other formats → parse_document. Fallback to normal parsing if OCR fails.
- Implemented sovereign/api/routes/vision_ocr.py: 5 new endpoints:
  - POST /vision/describe — general image description
  - POST /vision/diagram — engineering diagram description
  - POST /vision/inspect — inspection photo description
  - POST /ocr/image — standalone image OCR
  - POST /documents/{id}/re-ocr — re-run OCR on existing document
  Wired into app.py alongside health and documents routers.
- Wrote 2 new test files (32 new tests):
  - test_ocr.py: 24 tests across 5 test classes: TestTesseractAdapter (protocol compliance, text extraction, blank image, layout mode, confidence, page size, invalid image), TestScannedDetection (text PDF not scanned, scanned PDF detected, mixed PDF partially detected, char/image counts), TestPageRendering (PNG output, invalid page, DPI scaling), TestOCRPipeline (image→ParsedDocument, text extraction, scanned PDF OCR, text PDF preservation, mixed PDF, metadata, blank image), TestBackendRegistration (tesseract.ocr in registry).
  - test_vision.py: 5 tests: describe_image, describe_diagram, describe_inspection_image, extract_text_from_image, _normalize_media_type.
  - Added 3 new API integration tests in test_documents_api.py: image upload via API, vision/describe endpoint, ocr/image endpoint.
- Updated existing ingestion tests: made all test functions async (ingest_document is now async), added await to all ingest_document calls.
- Fixed lint: E741 (ambiguous variable `l` → `ln` in OCR helpers), E501 (line length in ingestion/service, vision/service, tests), RUF059 (unused unpacked variables in test), PLC0415 (per-file-ignores for ocr/ and api/routes/), removed unused type:ignore comments.
- Fixed mypy: fitz/PIL/pytesseract/docx import stubs via mypy override `ignore_missing_imports = true`, OCROptions.languages type as `list[str] | None` with `__post_init__` default, media_type Literal type mismatch via _normalize_media_type + type:ignore[arg-type], implicit Optional in route handlers (replaced GatewayDep=None with get_model_gateway() call), no-any-return for pix.tobytes().
- Verified end-to-end: uploaded a PNG image containing "INSPECTION ID: 2024-0042" and "STATUS: PASS", Tesseract OCR extracted the text perfectly, parsed document retrievable via API. Vision describe endpoint works with MockBackend.

Stage Summary:
- Phase 3 COMPLETE. 164/164 tests pass (132 Phase 1+2 + 32 Phase 3). Ruff clean. Mypy clean (48 files).
- Real Tesseract OCR working: text extraction from images with bounding boxes, confidence scores, and layout analysis.
- Scanned-PDF detection: text-density-based per-page detection handles text PDFs, fully scanned PDFs, and mixed PDFs.
- OCR pipeline integrated into ingestion: uploaded images auto-OCR'd, scanned PDFs auto-detected and OCR'd, mixed PDFs selectively OCR'd.
- Vision service: 4 specialized methods (general, diagram, inspection, text extraction) using the VisionLLM protocol — MockBackend in dev, real vision models in prod.
- 5 new API endpoints: /vision/describe, /vision/diagram, /vision/inspect, /ocr/image, /documents/{id}/re-ocr.
- Ready for Phase 4 (Knowledge base: embeddings + vector store + hybrid retrieval) upon user approval.

Artifacts produced:
- 4 new Python source files: ocr/__init__.py, ocr/tesseract.py, ocr/pipeline.py, vision/__init__.py, vision/service.py, api/routes/vision_ocr.py
- 2 new test files: tests/unit/test_ocr.py (24 tests), tests/unit/test_vision.py (5 tests)
- 3 new API integration tests in tests/integration/test_documents_api.py
- Updated: ingestion/service.py (async + OCR integration), models/backends/__init__.py (tesseract registration), api/app.py (vision_ocr router), pyproject.toml (pytesseract/Pillow deps, mypy overrides, per-file-ignores)

---
Task ID: phase-4
Agent: Principal Engineer (main)
Task: Phase 4 — Knowledge base. Build embeddings service, Qdrant vector store, BM25 keyword index, hybrid retrieval with RRF fusion, indexing service, wire into ingestion pipeline, and API routes.

Work Log:
- Implemented sovereign/embeddings/service.py: EmbeddingService using the EmbeddingModel protocol from ModelGateway. Methods: embed_chunks (batch embed chunks → (chunk, vector) pairs), embed_query (single query embedding), dim property. Uses MockEmbeddingModel in dev (hash-based, deterministic), real embedding models in prod.
- Implemented sovereign/storage/qdrant.py: QdrantStore — Qdrant vector store client with project-scoped collections (sovereign_<project_id>). Embedded mode for dev (in-process, no server), server mode for prod (via QDRANT_URL). Methods: ensure_collection (creates collection with COSINE distance if missing), upsert_chunks (stores vectors + payload metadata), search (nearest-neighbor query with optional document filter), delete_by_document, count_points. Uses query_points API (current) with fallback to deprecated search API. Point IDs are MD5-hash integers derived from chunk_ids for Qdrant compatibility.
- Implemented sovereign/retrieval/keyword.py: BM25Index — in-memory keyword index with standard BM25 ranking (k1=1.5, b=0.75). Tokenization: lowercase, word-boundary split, stopword removal. Methods: add_chunks, remove_chunk, remove_document, search (returns ranked KeywordSearchResult with provenance). Per-project isolation (separate index instances).
- Implemented sovereign/retrieval/fusion.py: reciprocal_rank_fusion — RRF algorithm combining multiple ranked lists. Formula: RRF(d) = sum of 1/(k + rank) across rankers, k=60 (standard). Returns FusedResult with per-ranker ranks for debugging.
- Implemented sovereign/retrieval/service.py: HybridRetriever — combines vector + keyword search with RRF fusion. Runs both searches in parallel, fuses ranked lists, returns unified RetrievalResult with provenance (page, section_path, chunk_index, block_kinds) and per-ranker ranks. Configurable top_k, RRF k, document filter. Document filter applied to both vector and keyword results.
- Implemented sovereign/embeddings/indexing.py: IndexingService — the bridge between parsing and retrieval. index_document: ParsedDocument → Chunker → EmbeddingService → QdrantStore + BM25Index. Manages per-project BM25 indexes in memory. remove_document clears from both stores. get_stats returns counts. Re-indexing replaces (not duplicates) chunks. Singleton factory with reset for tests.
- Updated sovereign/ingestion/service.py: ingest_document now auto-indexes after parsing. Documents go from "parsed" → "indexed" status. delete_document also removes from the knowledge base index. Indexing failures are non-fatal (logged as warning, document stays "parsed").
- Implemented sovereign/api/routes/knowledge_base.py: 4 new endpoints:
  - POST /documents/{id}/index — manually (re)index a document
  - POST /search — hybrid retrieval search with optional document_id filter
  - GET /kb/stats — knowledge base statistics (keyword count, vector count)
  - DELETE /documents/{id}/index — remove from index
  Wired into app.py.
- Wrote 3 new test files (40 new tests):
  - test_embeddings.py: 13 tests (EmbeddingService: embed_chunks, embed_query, dim, determinism, empty list; IndexingService: index_document, keyword+vector population, remove, reindex, stats, empty doc, project isolation)
  - test_retrieval.py: 18 tests (BM25Index: add/search, empty, no match, remove doc/chunk, top_k, provenance, tokenization; RRF: two lists, single list, empty, one-list-only, sorted scores, ranks included; HybridRetriever: retrieve, empty KB, top_k, provenance, document filter)
  - test_kb_api.py: 8 API integration tests (search empty KB, stats empty, upload+search, stats after indexing, manual reindex, remove from index, document filter, provenance in results)
- Updated existing tests: status assertions now accept "indexed" in addition to "parsed" (documents auto-index after upload).
- Fixed Qdrant API compatibility: .search() is deprecated in qdrant-client 1.19+, replaced with .query_points(). Added fallback for older API.
- Fixed document filter: keyword search results now also filtered by document_id (previously only vector results were filtered, causing cross-document leakage via RRF fusion).
- Fixed lint: E501 (line length in test fixtures), F841 (unused variables), removed unused type:ignore. Fixed mypy: removed unused type:ignore[attr-defined] in qdrant reset.

Stage Summary:
- Phase 4 COMPLETE. 204/204 tests pass (164 Phase 1-3 + 40 Phase 4). Ruff clean. Mypy clean (57 files).
- Full knowledge base pipeline: upload → parse → chunk → embed → index (Qdrant + BM25) → hybrid search.
- Qdrant embedded mode works in dev (in-process, no server). Server mode for prod via QDRANT_URL.
- BM25 keyword index with stopword removal and standard BM25 ranking (k1=1.5, b=0.75).
- Hybrid retrieval with RRF fusion (k=60) combining vector + keyword results.
- Per-project isolation: separate Qdrant collections, separate BM25 indexes.
- Document filter works across both vector and keyword search.
- 4 new API endpoints: POST /search, GET /kb/stats, POST /documents/{id}/index, DELETE /documents/{id}/index.
- End-to-end verified: uploaded pump report + valve report, searched "pump bearing wear" → found pump report, searched "valve leaking" → found valve report, document filter correctly restricted results.
- Ready for Phase 5 (Hybrid RAG: 9-stage pipeline with query rewriting, reranking, evidence verification) upon user approval.

Artifacts produced:
- 6 new Python source files: embeddings/__init__.py, embeddings/service.py, embeddings/indexing.py, storage/qdrant.py, retrieval/__init__.py, retrieval/keyword.py, retrieval/fusion.py, retrieval/service.py, api/routes/knowledge_base.py
- 3 new test files: tests/unit/test_embeddings.py (13 tests), tests/unit/test_retrieval.py (18 tests), tests/integration/test_kb_api.py (8 tests)
- Updated: ingestion/service.py (auto-indexing + index cleanup on delete), api/app.py (kb router), existing tests (status assertions)

---
Task ID: phase-5
Agent: Principal Engineer (main)
Task: Phase 5 — Hybrid RAG: 9-stage grounded retrieval pipeline. Build query understanding, rewriting, hybrid retrieval (reuse Phase 4), reranking, evidence selection, LLM reasoning (grounded, tool-role context), evidence verification (SUPPORTED/PARTIAL/UNSUPPORTED/CONFLICTING), and "insufficient evidence" as a first-class verdict.

Work Log:
- Implemented sovereign/rag/model.py: typed pipeline I/O — EvidenceRef (document_id, chunk_id, page, section_path, text), Claim (text, evidence, support_status), SupportStatus (SUPPORTED/PARTIALLY_SUPPORTED/UNSUPPORTED/CONFLICTING), Verdict (answered/insufficient_evidence/out_of_scope), QueryAnalysis (intent, key_terms, constraints, rewritten_queries), RAGResponse (query, verdict, answer, claims, evidence, pipeline_trace). Verdict.insufficient_evidence() is a first-class factory — "I don't have sufficient evidence" is a successful explicit response, not an error.
- Implemented sovereign/rag/understand.py (Stage 1): query understanding via LLM with structured JSON prompt. Intent classification (factual/procedural/analytical/comparative/definitional/conversational), key term extraction, constraint extraction. Falls back to heuristic classification (keyword-based) when LLM returns invalid JSON or in mock mode.
- Implemented sovereign/rag/rewrite.py (Stage 2): query expansion — original query + LLM-rewritten queries + keyword-focused query from extracted key terms. Deduplicates. Returns list of query strings for multi-query retrieval.
- Implemented sovereign/reranking/service.py (Stage 5): reranking via the Reranker protocol. Converts RetrievalResults → RerankCandidates, calls the reranker, maps back to RetrievalResults in new order. Uses MockReranker (Jaccard overlap) in dev, cross-encoder in prod.
- Implemented sovereign/rag/select.py (Stage 6): evidence selection with score threshold, top_k limit, and max_per_document diversity cap. Returns EvidenceRef objects with full provenance (document_id, chunk_id, page, section_path, text).
- Implemented sovereign/rag/reason.py (Stage 7): grounded answer generation. Evidence injected as `tool` role messages (NEVER `system`, per ADR 0003). System prompt explicitly instructs: answer ONLY from evidence, cite by [1][2], say "I don't have sufficient evidence" if evidence doesn't answer, never fabricate citations. Returns empty-evidence message if no evidence provided.
- Implemented sovereign/rag/verify.py (Stage 8): evidence verification. Splits answer into claims (sentence-level), verifies each claim against evidence via LLM with structured JSON prompt. Returns Claim objects with SupportStatus. Falls back to text-overlap heuristic (SUPPORTED >60% overlap, PARTIALLY_SUPPORTED >30%, UNSUPPORTED <30%) when LLM fails or in mock mode. Filters out short fragments, citation-only refs, and the insufficient-evidence message from claims.
- Implemented sovereign/rag/pipeline.py (Stage 9): RAGPipeline orchestrating all 9 stages. Configurable: retrieval_top_k=20, rerank_top_k=10, evidence_top_k=5, min_score=0.01, max_per_document=3, verify_claims=True, min_evidence_count=1, min_supported_claims_ratio=0.3. Returns insufficient_evidence verdict when: (a) <min_evidence_count chunks found, (b) LLM self-reports insufficient, (c) <30% of claims are SUPPORTED. Pipeline trace populated for debugging/audit. Singleton factory with reset for tests.
- Implemented sovereign/api/routes/rag.py: POST /rag/query endpoint. Accepts {query, document_id?}, returns {verdict, verdict_message, answer, claims[], evidence[], is_answered}. Wired into app.py.
- Wrote 2 new test files (37 new tests):
  - test_rag.py: 31 unit tests across 7 test classes: TestQueryUnderstanding (6: analysis type, heuristic intent detection for procedural/definitional/comparative/analytical, key term extraction), TestQueryRewriting (4: original-first, keyword query, rewritten queries, dedup), TestReranking (1: count preservation + relevance ordering), TestEvidenceSelection (5: EvidenceRef type, top_k, min_score, max_per_document, empty), TestLLMReasoning (2: with/without evidence), TestEvidenceVerification (6: claim extraction, heuristic verify supported/unsupported/partial, verify_answer returns claims), TestRAGPipeline (6: full pipeline with indexed content, insufficient evidence on empty KB, claims returned, evidence provenance, pipeline trace, document filter)
  - test_rag_api.py: 6 API integration tests (empty KB, indexed doc query, citations, document filter, response structure, empty query rejected)
- Fixed lint: E501 (line length in pipeline config, system prompts, test fixtures), PLW2901 (for-loop variable `s` shadowing → renamed to `sent`), removed unused type:ignore.
- Fixed mypy: SupportStatus return type annotation — cast json.loads result to str, validate against tuple of valid statuses before returning.
- End-to-end verified: uploaded pump manual → queried "How often does pump P-101 need maintenance?" → pipeline ran all 9 stages → evidence found (2 chunks) → LLM generated answer → evidence verification flagged claims as UNSUPPORTED (mock LLM doesn't produce grounded answers) → pipeline returned insufficient_evidence verdict. This is correct behavior: the system prefers "I don't know" over hallucination. With a real LLM, claims would be SUPPORTED and verdict would be "answered".

Stage Summary:
- Phase 5 COMPLETE. 241/241 tests pass (204 Phase 1-4 + 37 Phase 5). Ruff clean. Mypy clean (68 files).
- 9-stage RAG pipeline implemented exactly as specified: understand → rewrite → retrieve → filter → rerank → select → reason → verify → respond.
- "I don't have sufficient evidence to answer this" is a first-class Verdict, returned when: evidence count < threshold, LLM self-reports insufficient, or <30% of claims are SUPPORTED.
- Evidence injected as `tool` role (NEVER `system`) per ADR 0003 — prompt injection defense.
- Every claim carries support_status (SUPPORTED/PARTIALLY_SUPPORTED/UNSUPPORTED/CONFLICTING) — flows through to deliverable rendering (Phase 10).
- Pipeline trace populated for debugging and audit.
- API endpoint: POST /rag/query with document filter support.
- Ready for Phase 6 (Evidence/citations: structured citation model + rendering) upon user approval.

Artifacts produced:
- 9 new Python source files: rag/__init__.py, rag/model.py, rag/understand.py, rag/rewrite.py, rag/select.py, rag/reason.py, rag/verify.py, rag/pipeline.py, reranking/__init__.py, reranking/service.py, api/routes/rag.py
- 2 new test files: tests/unit/test_rag.py (31 tests), tests/integration/test_rag_api.py (6 tests)
- Updated: api/app.py (rag router)

---
Task ID: phase-6
Agent: Principal Engineer (main)
Task: Phase 6 — Evidence/citations. Build structured citation model, evidence collector with deduplication, contradiction detector, citation renderer (markdown/inline/structured), integrate into RAG pipeline, and add API endpoints.

Work Log:
- Implemented sovereign/evidence/model.py: typed citation model — Citation (citation_id, document_id, document_filename, chunk_id, page, section_path, evidence_text, support_status, support_note, relevance_score; properties: section_label, source_label), Contradiction (conflict_type, description, citation_ids, conflicting_texts), ConflictType (value_mismatch/contradictory_facts/temporal_conflict/scope_conflict), EvidenceReport (query, citations, contradictions; properties: citation_count, supported/partially/unsupported/conflicting counts, has_contradictions, unique_documents, summary).
- Implemented sovereign/evidence/collector.py: EvidenceCollector — converts RetrievalResults to Citations with deduplication (by chunk_id), source diversity (max_per_document cap), score threshold filtering, filename lookup from DB. Returns stable citation_ids (cit_000, cit_001, ...).
- Implemented sovereign/evidence/contradictions.py: ContradictionDetector — two detection strategies: (1) value_mismatch: regex extraction of number+unit pairs, groups by context (preceding words), flags different values for same parameter (e.g. "150 PSI" vs "200 PSI"); (2) contradictory_facts: pattern matching for common contradiction pairs (operational/failed, pass/fail, open/closed, safe/unsafe, etc.). Returns Contradiction objects linking conflicting citations.
- Implemented sovereign/evidence/renderer.py: CitationRenderer — 4 rendering modes: (1) render_markdown: full evidence report as markdown with summary, numbered citations with status icons, contradictions section; (2) render_inline: compact [1] source; [2] source format for answer appending; (3) render_structured: JSON-serializable dict for API responses; (4) render_citation_list: simple numbered/bulleted list.
- Updated sovereign/rag/model.py: RAGResponse now includes evidence_report field (EvidenceReport, typed as object|None to avoid circular import) and has_contradictions property.
- Updated sovereign/rag/pipeline.py: RAGPipeline now builds EvidenceReport after evidence selection (stage 6). Uses EvidenceCollector to convert reranked results to Citations, runs ContradictionDetector, attaches report to all RAGResponse returns. After evidence verification (stage 8), updates citation support_status to CONFLICTING for citations involved in contradictions. Pipeline trace includes evidence_citations and evidence_contradictions counts.
- Updated sovereign/api/routes/rag.py: POST /rag/query response now includes full evidence_report (citations[], contradictions[], summary, has_contradictions). Added POST /rag/query/markdown endpoint that returns the answer + claims + rendered evidence report as markdown (text/markdown content type).
- Wrote tests/unit/test_evidence.py: 31 tests across 5 test classes: TestCitationModel (5: section_label, source_label with/without page, fallback to doc_id), TestEvidenceReport (4: summary, unique_documents, has_contradictions, counts), TestEvidenceCollector (8: returns citations, dedup by chunk_id, max_total, max_per_document, min_score filter, empty, citation_id assignment, provenance preservation), TestContradictionDetector (6: single citation no contradictions, value mismatch detection, contradictory facts detection, no false positive on consistent values, citation_ids included, pass/fail detection), TestCitationRenderer (8: markdown with/without citations, markdown with contradictions, inline format, inline empty, structured dict, numbered list, summary in markdown).
- Fixed lint: E501 (line length in model, tests), PLR0912/PLR0915 (per-file-ignores for rag/), PLR0917 (per-file-ignores for tests), fixed __init__.py import source for Contradiction (from model not contradictions).
- Fixed mypy: EvidenceReport typed as object|None in RAGResponse (avoids circular import), _build_evidence_report uses typing.Any + cast for dict access from render_structured, removed unused type:ignore comments.
- End-to-end verified: uploaded pump manual → RAG query → evidence report with 2 citations, each with full provenance (source_label: "pump_manual.txt"), summary stats correct (2 supported, 0 contradictions), markdown endpoint produces formatted output with Evidence & Citations section.

Stage Summary:
- Phase 6 COMPLETE. 272/272 tests pass (241 Phase 1-5 + 31 Phase 6). Ruff clean. Mypy clean (73 files).
- Structured citation model: every claim traceable to (document_id, page, section_path, chunk_id, evidence_text, support_status).
- Contradiction detection: value_mismatch (numerical parameter conflicts) + contradictory_facts (status word conflicts like operational/failed).
- 4 citation rendering modes: markdown (full report), inline ([1] source format), structured (JSON dict), numbered list.
- RAG pipeline now produces EvidenceReport alongside every RAGResponse — flows through to API and deliverables.
- API: POST /rag/query includes full evidence_report; POST /rag/query/markdown returns rendered markdown.
- Ready for Phase 7 (Agent orchestration: LangGraph supervisor + sub-agents) upon user approval.

Artifacts produced:
- 5 new Python source files: evidence/__init__.py, evidence/model.py, evidence/collector.py, evidence/contradictions.py, evidence/renderer.py
- 1 new test file: tests/unit/test_evidence.py (31 tests)
- Updated: rag/model.py (evidence_report field), rag/pipeline.py (EvidenceReport construction + contradiction detection), api/routes/rag.py (evidence_report in response + markdown endpoint), evidence/__init__.py, pyproject.toml (per-file-ignores)
