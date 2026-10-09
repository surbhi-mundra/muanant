# SOVEREIGN — Security

SOVEREIGN is designed for confidential industrial work. This document is
the authoritative controls matrix; the implementation lives in
`sovereign/security/`, `sovereign/audit/`, `configs/policies.yaml`, and the
middleware in `sovereign/api/middleware.py`.

## Threat model

The adversaries we defend against:

1. **Outsider via malicious document** — an uploaded PDF/DOCX contains an
   exploit for the parser, an embedded script, or a prompt-injection payload.
2. **Insider via privilege creep** — a user attempts to access another
   project's documents or escalate their role.
3. **Model exfiltration** — a malicious document tricks the LLM into
   emitting confidential document content to the Research Agent's egress path.
4. **Audit tampering** — an insider (or compromised account) attempts to
   rewrite audit history.
5. **Cloud creep** — a future engineer adds a "convenient" cloud API call,
   violating the on-prem mandate.
6. **Supply chain** — a dependency ships a backdoor.

## Controls matrix

| # | Threat | Control | Status |
|---|---|---|---|
| S1 | Prompt injection from documents | Retrieved/extracted text is `tool`/`user` role, never `system`. Canary tokens in KB text flag exfil attempts. Output validators. Per-agent tool allow-list. | Spec in ADR 0003; enforcement in Phase 5/7/11 |
| S2 | Malicious documents | Quarantine dir; `qpdf --check` before parse; PyMuPDF in restricted mode; size+page caps; parse in subprocess with timeout + memory limit. | Phase 2 |
| S3 | Path traversal | Storage keys are opaque UUIDs, never user filenames. Single `Storage` abstraction enforces `project_id`-scoped paths. | Phase 2 |
| S4 | Secrets leakage | No secrets in code; `pydantic-settings` from env/vault; `redactor` processor in `core/logging.py` scrubs known-secret keys + patterns. | ✅ Phase 1 |
| S5 | Uncontrolled egress | Egress gateway with allow-list; off by default; Research Agent is the only opt-in path and has no KB access. | Phase 11 |
| S6 | RBAC / project isolation | Postgres RLS on `project_id`; mandatory `project_id` filter on every Qdrant query; JWT with project scopes. | Phase 11 (RLS); filter pattern established Phase 4 |
| S7 | Audit tampering | Append-only `audit_events` table; hash-chained; separate write role; periodic `verify_audit_chain.py` cron. | ✅ Phase 1 (chain); Phase 11 (separate role + cron) |
| S8 | At-rest encryption | LUKS/dm-crypt for volumes; app-level envelope encryption for document blobs; keys in OS keyring/external KMS. | Phase 11 |
| S9 | Sandboxed tool execution | Tool calls run in subprocess + seccomp/namespace; per-agent allow-list. | Phase 7/11 |
| S10 | Inference server exposure | vLLM/Ollama bind to `127.0.0.1` only; never exposed to user network; mTLS between API and inference. | Phase 14 |
| S11 | AuthN weakness | OIDC (Keycloak/Authentik) for org SSO; local fallback with Argon2; session rotation; MFA for admin actions. | Phase 11 |
| S12 | Supply chain | `uv` lockfile pinned; `pip-audit` in CI; review of any dep with network access; `make audit` target. | ✅ Phase 1 (CI scaffold) |

## Critical invariants (do not violate)

1. **Retrieved text is data, not instruction.** Never inject KB chunks as
   `system` role. See ADR 0003.
2. **Egress is off by default.** `EGRESS_ENABLED=false` is the default in
   `.env.example`, `configs/dev.yaml`, `configs/prod.yaml`. Enabling it is
   a deliberate policy act, never a code change.
3. **No cloud APIs in the confidential execution path.** No OpenAI,
   Anthropic, Gemini, Cohere, cloud OCR, cloud embeddings, cloud vector DB.
   The ModelGateway's backend registry is the only path to model calls; new
   backends must be reviewed before registration.
4. **Audit log is append-only.** No `UPDATE` or `DELETE` on `audit_events`.
   The hash chain makes silent tampering detectable; the write role
   restriction (Phase 11) makes it impossible from the app layer.
5. **Project isolation is mandatory.** Every DB query and Qdrant query must
   filter by `project_id`. No "all projects" queries except in admin tools
   that explicitly check the admin role.
6. **Storage paths are opaque.** Document filenames are stored in
   `documents.original_filename` for display; the actual object store key
   is `documents.storage_key`, an opaque UUID. Never resolve a user-supplied
   filename to a filesystem path.

## Reporting a security issue

Internal: file a confidential ticket and notify the security lead. Do NOT
commit a proof-of-concept exploit to the repo.
