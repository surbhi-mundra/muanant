"""SOVEREIGN — On-Premise Agentic AI Workbench.

Top-level package. Submodules:

- ``core``       — shared kernel: config, logging, ids, errors, telemetry
- ``models``     — ModelGateway: protocol interfaces + adapters (model-agnostic)
- ``storage``    — DB models, Alembic, vector store, object store
- ``ingestion``  — secure upload, quarantine, validation, versioning
- ``parsing``    — structure-preserving parsers per format
- ``ocr``        — OCR pipeline (pluggable engine)
- ``vision``     — multimodal processing
- ``embeddings`` — embedding + indexing
- ``retrieval``  — hybrid retrieval + fusion
- ``reranking``  — cross-encoder reranker
- ``rag``        — 9-stage grounded retrieval pipeline
- ``evidence``   — claim / evidence / provenance model + verifier
- ``agents``     — LangGraph supervisor + sub-agents
- ``orchestration`` — graph wiring, checkpointer, HITL
- ``risk``       — findings, severity, recommendations
- ``deliverables`` — report templates + exporters
- ``approvals``  — human-in-the-loop queue
- ``security``   — egress, sandbox, injection guards, RBAC
- ``audit``      — append-only hash-chained audit log
- ``api``        — FastAPI app, routes, auth

Phase 1 ships only: ``core``, ``models``, ``storage``, ``audit``, ``api``.
"""

__version__ = "0.1.0"
