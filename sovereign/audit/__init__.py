"""SOVEREIGN audit — append-only, hash-chained audit log.

Every meaningful action in the system writes a row to ``audit_events``:
- authentication (login, logout, failed)
- document ingestion, deletion, re-index
- retrieval queries (without the query text — only metadata)
- agent invocations (which agent, what tools, what model)
- approval requests and decisions
- egress attempts (allowed and blocked)
- security events (injection attempts, quarantine triggers)

The log is hash-chained: each row's ``hash`` field is the SHA-256 of
``prev_hash || canonical_json(payload)``. Tampering with any row other than
the last breaks the chain. ``scripts/verify_audit_chain.py`` validates this
periodically (cron job in prod).

Payloads must NOT contain confidential document content. The payload schema
in ``AuditEventPayload`` is intentionally restricted to metadata: IDs,
counts, durations, model names, status codes. If you need to log something
sensitive, log a *hash* of it, not the value.
"""
