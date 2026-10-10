"use client";

import { useState } from "react";

const CATEGORIES = [
  {
    name: "Document Operations",
    color: "#6366f1",
    events: ["document.uploaded", "document.deleted", "document.indexed"],
  },
  {
    name: "Queries & Retrieval",
    color: "#3b82f6",
    events: ["search.executed", "rag.query", "rag.answered"],
  },
  {
    name: "Agent Activity",
    color: "#10b981",
    events: ["agent.started", "agent.step", "agent.completed", "agent.failed"],
  },
  {
    name: "Deliverables",
    color: "#f59e0b",
    events: ["deliverable.created", "deliverable.exported"],
  },
  {
    name: "System",
    color: "#a1a1aa",
    events: ["system.startup", "system.health", "config.changed"],
  },
];

const PROPERTIES = [
  { name: "timestamp", type: "ISO 8601 UTC", description: "When the event occurred" },
  { name: "event", type: "string", description: "Dotted event identifier" },
  { name: "actor", type: "string", description: "User or system that triggered it" },
  { name: "resource_id", type: "string", description: "ID of the affected resource" },
  { name: "hash", type: "sha256", description: "Content hash of the event payload" },
  { name: "prev_hash", type: "sha256", description: "Hash of the previous entry" },
];

export default function AuditPage() {
  const [copied, setCopied] = useState(false);

  const verifyCmd = `sovereign audit verify --chain /var/lib/sovereign/audit.chain \\
  --since "$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)"`;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(verifyCmd);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // ignore
    }
  };

  return (
    <div className="sov-fade-in">
      <PageHeader
        eyebrow="System"
        title="Audit"
        description="Every action in SOVEREIGN is recorded to a tamper-evident, hash-chained audit log. Verify integrity on-premise at any time."
      />

      <div className="px-8 pb-12 max-w-[1200px] mx-auto space-y-6">
        {/* Hero / explanation */}
        <section className="sov-card p-6">
          <div className="flex items-start gap-4">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
              style={{
                background:
                  "linear-gradient(135deg, rgba(99,102,241,0.18) 0%, rgba(99,102,241,0.06) 100%)",
                border: "1px solid rgba(99,102,241,0.3)",
                color: "var(--color-primary)",
              }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6">
                <path d="M12 2 4 5v6c0 5 3.5 9 8 11 4.5-2 8-6 8-11V5l-8-3z" />
                <path d="m9 12 2 2 4-4" />
              </svg>
            </div>
            <div className="flex-1">
              <h2 className="text-[16px] font-semibold text-white">
                Tamper-Evident Audit Chain
              </h2>
              <p className="text-[13px] text-zinc-400 mt-1.5 leading-relaxed">
                Each event is hashed (SHA-256) and chained to the previous event's hash.
                Any modification to a historical entry invalidates every subsequent hash,
                making tampering immediately detectable. The chain is stored locally on
                the same machine as the workbench — no data leaves your premises.
              </p>
              <div className="flex flex-wrap gap-2 mt-4">
                <span className="sov-badge badge-supported">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-3 h-3">
                    <path d="m5 12 5 5L20 7" />
                  </svg>
                  SHA-256 chained
                </span>
                <span className="sov-badge badge-info">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-3 h-3">
                    <path d="m5 12 5 5L20 7" />
                  </svg>
                  On-premise storage
                </span>
                <span className="sov-badge badge-primary">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-3 h-3">
                    <path d="m5 12 5 5L20 7" />
                  </svg>
                  Verifiable offline
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Verification command */}
        <section className="sov-card p-6">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-[15px] font-semibold text-white">
                Verify the Chain
              </h2>
              <p className="text-[12.5px] text-zinc-500 mt-0.5">
                Run this command on the SOVEREIGN host to validate integrity.
              </p>
            </div>
            <button onClick={copy} className="sov-btn sov-btn-secondary">
              {copied ? (
                <svg viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                  <path d="m5 12 5 5L20 7" />
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                  <rect x="9" y="9" width="13" height="13" rx="2" />
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                </svg>
              )}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <div
            className="rounded-lg overflow-hidden"
            style={{
              background: "#070708",
              border: "1px solid var(--color-border)",
            }}
          >
            <div
              className="flex items-center gap-1.5 px-4 py-2.5 border-b"
              style={{ borderColor: "var(--color-border)" }}
            >
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: "#ef4444" }} />
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: "#f59e0b" }} />
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: "#10b981" }} />
              <span className="ml-2 text-[11px] text-zinc-500 font-mono">bash — sovereign@workbench</span>
            </div>
            <pre
              className="px-4 py-4 text-[12.5px] font-mono leading-relaxed overflow-x-auto"
              style={{ color: "#e4e4e7" }}
            >
              <span style={{ color: "#71717a" }}>$</span>{" "}
              <span style={{ color: "#818cf8" }}>sovereign</span>{" "}
              <span style={{ color: "#34d399" }}>audit</span>{" "}
              <span style={{ color: "#fcd34d" }}>verify</span>{" "}
              <span style={{ color: "#a1a1aa" }}>--chain</span>{" "}
              <span style={{ color: "#fafafa" }}>/var/lib/sovereign/audit.chain</span>{" "}
              <span style={{ color: "#a1a1aa" }}> \{"\n"}</span>
              {"  "}
              <span style={{ color: "#a1a1aa" }}>--since</span>{" "}
              <span style={{ color: "#fafafa" }}>"$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)"</span>
              {"\n\n"}
              <span style={{ color: "#71717a" }}># ✓ Chain intact · 1,284 events verified · 0 tampered</span>
              {"\n"}
              <span style={{ color: "#71717a" }}># ✓ Latest hash: 7a3f…b9c2 matches stored head</span>
            </pre>
          </div>
        </section>

        {/* Categories */}
        <section className="sov-card p-6">
          <h2 className="text-[15px] font-semibold text-white mb-1">
            Event Categories
          </h2>
          <p className="text-[12.5px] text-zinc-500 mb-4">
            Every action is recorded with one of the following event types.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {CATEGORIES.map((c) => (
              <div
                key={c.name}
                className="p-4 rounded-lg"
                style={{
                  background: "var(--color-surface-2)",
                  border: "1px solid var(--color-border)",
                }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ background: c.color }}
                  />
                  <h3 className="text-[13px] font-semibold text-zinc-100">
                    {c.name}
                  </h3>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {c.events.map((e) => (
                    <code
                      key={e}
                      className="text-[11px] px-2 py-0.5 rounded font-mono"
                      style={{
                        background: "var(--color-surface-3)",
                        border: "1px solid var(--color-border)",
                        color: "var(--color-text-muted)",
                      }}
                    >
                      {e}
                    </code>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Entry shape */}
        <section className="sov-card p-6">
          <h2 className="text-[15px] font-semibold text-white mb-1">
            Audit Entry Shape
          </h2>
          <p className="text-[12.5px] text-zinc-500 mb-4">
            Each entry in the chain contains these fields.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr
                  className="text-left"
                  style={{
                    background: "var(--color-surface-2)",
                    borderBottom: "1px solid var(--color-border)",
                  }}
                >
                  <th className="px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">Field</th>
                  <th className="px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">Type</th>
                  <th className="px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">Description</th>
                </tr>
              </thead>
              <tbody>
                {PROPERTIES.map((p) => (
                  <tr
                    key={p.name}
                    className="border-b last:border-0"
                    style={{ borderColor: "var(--color-border)" }}
                  >
                    <td className="px-4 py-2.5">
                      <code className="text-[12.5px] font-mono text-indigo-300">
                        {p.name}
                      </code>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="sov-badge badge-neutral">{p.type}</span>
                    </td>
                    <td className="px-4 py-2.5 text-[12.5px] text-zinc-400">
                      {p.description}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Footer note */}
        <section
          className="flex items-start gap-3 p-4 rounded-lg"
          style={{
            background: "rgba(59, 130, 246, 0.06)",
            border: "1px solid rgba(59, 130, 246, 0.25)",
          }}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="var(--color-info)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5 shrink-0 mt-0.5">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 16v-4M12 8h.01" />
          </svg>
          <div className="text-[12.5px] text-zinc-300 leading-relaxed">
            <strong className="text-white">Note:</strong> The audit chain is append-only
            and replicated to local disk. For maximum assurance, mirror the chain file to
            a separate write-once storage system or WORM media on a regular cadence.
          </div>
        </section>
      </div>
    </div>
  );
}

/* ---------- Local UI ---------- */

function PageHeader({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <header
      className="px-8 pt-8 pb-6 border-b mb-8 sov-grid-bg"
      style={{
        background: "linear-gradient(180deg, rgba(99,102,241,0.04) 0%, transparent 100%)",
        borderColor: "var(--color-border)",
      }}
    >
      <div className="max-w-[1200px] mx-auto">
        <div className="eyebrow mb-2">{eyebrow}</div>
        <h1 className="text-[26px] font-semibold tracking-tight text-white text-balance">
          {title}
        </h1>
        <p className="text-[13.5px] text-zinc-400 mt-2 max-w-2xl leading-relaxed">
          {description}
        </p>
      </div>
    </header>
  );
}
