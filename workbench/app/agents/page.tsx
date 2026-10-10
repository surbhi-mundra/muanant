"use client";

import { useState } from "react";
import { agentQuery } from "@/lib/api";

type Step = {
  name?: string;
  status?: "pending" | "running" | "completed" | "failed";
  description?: string;
  started_at?: string;
  completed_at?: string;
};

type Finding = {
  title?: string;
  description?: string;
  severity?: "critical" | "high" | "medium" | "low" | "info";
  recommendation?: string;
  evidence?: string;
};

type AgentResponse = {
  task_type?: string;
  task_summary?: string;
  steps?: Step[];
  pipeline?: Step[];
  findings?: Finding[];
  deliverable?: {
    title?: string;
    format?: string;
    content?: string;
    markdown?: string;
    preview?: string;
  };
  deliverable_preview?: string;
  deliverable_markdown?: string;
  metadata?: any;
};

function severityBadge(s?: string) {
  switch (s) {
    case "critical":
      return { cls: "badge-critical", label: "CRITICAL" };
    case "high":
      return { cls: "badge-high", label: "HIGH" };
    case "medium":
      return { cls: "badge-medium", label: "MEDIUM" };
    case "low":
      return { cls: "badge-low", label: "LOW" };
    case "info":
      return { cls: "badge-info", label: "INFO" };
    default:
      return { cls: "badge-neutral", label: "—" };
  }
}

function taskTypeBadge(t?: string) {
  if (!t) return { cls: "badge-neutral", label: "AUTO" };
  const lower = t.toLowerCase();
  if (lower.includes("risk") || lower.includes("hazard")) {
    return { cls: "badge-critical", label: t.toUpperCase() };
  }
  if (lower.includes("compliance") || lower.includes("audit")) {
    return { cls: "badge-info", label: t.toUpperCase() };
  }
  if (lower.includes("incid")) {
    return { cls: "badge-high", label: t.toUpperCase() };
  }
  return { cls: "badge-primary", label: t.toUpperCase() };
}

const EXAMPLES = [
  "Analyze safety risks in the high-pressure pipeline operating procedures.",
  "Investigate compliance gaps in our supplier qualification process.",
  "Review the incident response plan and surface critical weaknesses.",
  "Audit the warranty claims workflow for fraud risk.",
];

export default function AgentsPage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<AgentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (q?: string) => {
    const finalQuery = (q ?? query).trim();
    if (!finalQuery || loading) return;
    if (q) setQuery(q);
    setLoading(true);
    setError(null);
    setResponse(null);
    try {
      const resp: AgentResponse = await agentQuery({ query: finalQuery });
      setResponse(resp);
    } catch (e: any) {
      setError(e?.message || "Agent query failed");
    } finally {
      setLoading(false);
    }
  };

  const steps = response?.steps_completed || response?.steps || [];
  const findings = response?.findings || [];
  const deliverableContent =
    response?.deliverable?.markdown ||
    response?.deliverable?.content ||
    response?.deliverable?.preview ||
    "";
  const taskBadge = taskTypeBadge(response?.task_type);

  return (
    <div className="sov-fade-in">
      <PageHeader
        eyebrow="Intelligence"
        title="Agents"
        description="Run multi-step agent investigations. The agent plans, retrieves, analyzes, and synthesizes findings — then drafts a deliverable you can review and export."
      />

      <div className="px-8 pb-12 max-w-[1200px] mx-auto space-y-6">
        {/* Query input */}
        <section className="sov-card p-5">
          <label className="eyebrow block mb-2">Investigation Query</label>
          <div className="flex gap-2">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run();
              }}
              placeholder="Describe what you want the agent to investigate…"
              className="sov-input flex-1"
              rows={3}
              style={{ minHeight: 80 }}
            />
            <button
              onClick={() => run()}
              disabled={loading || !query.trim()}
              className="sov-btn sov-btn-primary self-end"
              style={{ height: 42 }}
            >
              {loading ? <span className="sov-spinner" /> : null}
              {loading ? "Running…" : "Run Agent"}
            </button>
          </div>
          {!response && !loading && (
            <div className="flex items-center gap-2 mt-3 flex-wrap">
              <span className="text-[11.5px] text-zinc-500">Try:</span>
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => run(ex)}
                  className="text-[12px] px-2.5 py-1 rounded-full border transition-colors hover:border-indigo-500/50 hover:text-indigo-300 text-left"
                  style={{
                    background: "var(--color-surface-2)",
                    borderColor: "var(--color-border)",
                    color: "var(--color-text-muted)",
                  }}
                >
                  {ex.length > 60 ? ex.slice(0, 60) + "…" : ex}
                </button>
              ))}
            </div>
          )}
        </section>

        {/* Error */}
        {error && !loading && (
          <div
            className="flex items-start gap-3 p-4 rounded-lg"
            style={{
              background: "rgba(239, 68, 68, 0.06)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
            }}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="var(--color-danger)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5 shrink-0 mt-0.5">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 8v4M12 16h.01" />
            </svg>
            <div className="flex-1">
              <div className="text-[13px] font-medium text-red-300">Agent failed</div>
              <div className="text-[12px] text-red-400/80 mt-0.5">{error}</div>
            </div>
          </div>
        )}

        {/* Loading pipeline */}
        {loading && (
          <section className="sov-card p-6">
            <div className="flex items-center gap-3 mb-5">
              <span className="sov-spinner sov-spinner-lg" />
              <div>
                <div className="text-[14px] font-semibold text-white">
                  Agent running…
                </div>
                <div className="text-[12.5px] text-zinc-500 mt-0.5">
                  Planning · Retrieving · Analyzing · Synthesizing
                </div>
              </div>
            </div>
            <div className="space-y-4 pl-1">
              {["Plan", "Retrieve", "Analyze", "Synthesize", "Draft deliverable"].map(
                (s, i) => (
                  <div key={s} className="sov-step">
                    {i < 4 && <div className="sov-step-line" />}
                    <div className="sov-step-icon">
                      {i === 0 ? (
                        <span className="sov-spinner" style={{ width: 12, height: 12 }} />
                      ) : (
                        <span className="w-1.5 h-1.5 rounded-full bg-current" />
                      )}
                    </div>
                    <div className="flex-1 pb-1">
                      <div className="text-[13px] font-medium text-zinc-300">{s}</div>
                      <div className="text-[11.5px] text-zinc-500 mt-0.5">
                        {i === 0 ? "Working…" : "Pending"}
                      </div>
                    </div>
                  </div>
                )
              )}
            </div>
          </section>
        )}

        {/* Response */}
        {response && !loading && (
          <div className="space-y-5 sov-fade-in">
            {/* Task summary */}
            <section className="sov-card p-5">
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] uppercase tracking-wider font-semibold text-zinc-500">
                    Task
                  </span>
                  <span className={`sov-badge ${taskBadge.cls}`}>{taskBadge.label}</span>
                </div>
              </div>
              {response.task_summary && (
                <p className="text-[14px] leading-relaxed text-zinc-100">
                  {response.task_summary}
                </p>
              )}
            </section>

            {/* Pipeline */}
            {steps.length > 0 && (
              <section className="sov-card p-5">
                <h3 className="text-[12px] uppercase tracking-wider font-semibold text-zinc-500 mb-4">
                  Agent Pipeline
                </h3>
                <div className="space-y-4 pl-1">
                  {steps.map((s, i) => {
                    const status = s.status || "completed";
                    const cls =
                      status === "completed"
                        ? "sov-step-done"
                        : status === "running"
                        ? "sov-step-active"
                        : status === "failed"
                        ? ""
                        : "";
                    return (
                      <div key={i} className={`sov-step ${cls}`}>
                        {i < steps.length - 1 && <div className="sov-step-line" />}
                        <div
                          className="sov-step-icon"
                          style={
                            status === "failed"
                              ? {
                                  background: "rgba(239,68,68,0.15)",
                                  borderColor: "rgba(239,68,68,0.4)",
                                  color: "var(--color-danger)",
                                }
                              : undefined
                          }
                        >
                          {status === "completed" ? (
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
                              <path d="m5 12 5 5L20 7" />
                            </svg>
                          ) : status === "running" ? (
                            <span className="sov-spinner" style={{ width: 12, height: 12, borderTopColor: "#fff" }} />
                          ) : status === "failed" ? (
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
                              <path d="M18 6 6 18M6 6l12 12" />
                            </svg>
                          ) : (
                            <span className="w-1.5 h-1.5 rounded-full bg-current" />
                          )}
                        </div>
                        <div className="flex-1 pb-1">
                          <div className="text-[13px] font-medium text-zinc-200">
                            {s.name || `Step ${i + 1}`}
                          </div>
                          {s.description && (
                            <div className="text-[12px] text-zinc-500 mt-0.5 leading-relaxed">
                              {s.description}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* Findings */}
            {findings.length > 0 && (
              <section className="sov-card p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-[12px] uppercase tracking-wider font-semibold text-zinc-500">
                    Findings · {findings.length}
                  </h3>
                </div>
                <div className="space-y-2.5">
                  {findings.map((f, i) => {
                    const sev = severityBadge(f.severity);
                    return (
                      <div
                        key={i}
                        className="p-4 rounded-lg"
                        style={{
                          background: "var(--color-surface-2)",
                          border: "1px solid var(--color-border)",
                          borderLeftWidth: 3,
                          borderLeftColor:
                            f.severity === "critical"
                              ? "var(--color-danger)"
                              : f.severity === "high"
                              ? "var(--color-orange)"
                              : f.severity === "medium"
                              ? "var(--color-warning)"
                              : f.severity === "low"
                              ? "var(--color-success)"
                              : "var(--color-info)",
                        }}
                      >
                        <div className="flex items-start justify-between gap-3 mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] font-mono text-zinc-500">
                              F{i + 1}
                            </span>
                            <h4 className="text-[13.5px] font-semibold text-zinc-100">
                              {f.title || `Finding ${i + 1}`}
                            </h4>
                          </div>
                          <span className={`sov-badge ${sev.cls} shrink-0`}>
                            {sev.label}
                          </span>
                        </div>
                        {f.description && (
                          <p className="text-[12.5px] text-zinc-400 leading-relaxed">
                            {f.description}
                          </p>
                        )}
                        {f.recommendation && (
                          <div
                            className="mt-2.5 pt-2.5 flex items-start gap-2"
                            style={{ borderTop: "1px solid var(--color-border)" }}
                          >
                            <svg viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 mt-0.5 shrink-0">
                              <path d="m9 12 2 2 4-4" />
                              <circle cx="12" cy="12" r="10" />
                            </svg>
                            <div>
                              <div className="text-[11px] uppercase tracking-wider font-semibold text-zinc-500 mb-0.5">
                                Recommendation
                              </div>
                              <div className="text-[12.5px] text-zinc-300 leading-relaxed">
                                {f.recommendation}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* Deliverable preview */}
            {deliverableContent && (
              <section className="sov-card p-5">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-[12px] uppercase tracking-wider font-semibold text-zinc-500">
                      Deliverable Preview
                    </h3>
                    {response?.deliverable?.title && (
                      <p className="text-[14px] font-medium text-zinc-100 mt-1">
                        {response.deliverable.title}
                      </p>
                    )}
                  </div>
                  {response?.deliverable?.format && (
                    <span className="sov-badge badge-neutral">
                      {response.deliverable.format}
                    </span>
                  )}
                </div>
                <div
                  className="rounded-lg p-4 sov-scroll-y"
                  style={{
                    background: "var(--color-bg)",
                    border: "1px solid var(--color-border)",
                    maxHeight: 480,
                  }}
                >
                  <MarkdownPreview content={deliverableContent} />
                </div>
              </section>
            )}
          </div>
        )}
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

/**
 * Tiny, safe markdown-to-HTML renderer for preview purposes.
 * Handles headings, bold, italic, code, lists, links, hr, and paragraphs.
 */
function MarkdownPreview({ content }: { content: string }) {
  const html = renderMarkdown(content);
  return (
    <div
      className="sov-prose"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function escapeHtml(s: string) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderMarkdown(src: string): string {
  const lines = src.split(/\r?\n/);
  const out: string[] = [];
  let inList = false;
  let inOl = false;
  let inCode = false;
  let codeBuf: string[] = [];

  const closeList = () => {
    if (inList) {
      out.push("</ul>");
      inList = false;
    }
    if (inOl) {
      out.push("</ol>");
      inOl = false;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith("```")) {
      if (inCode) {
        out.push(`<pre><code>${escapeHtml(codeBuf.join("\n"))}</code></pre>`);
        codeBuf = [];
        inCode = false;
      } else {
        closeList();
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      codeBuf.push(line);
      continue;
    }

    // Headings
    const h = /^(#{1,6})\s+(.*)$/.exec(line);
    if (h) {
      closeList();
      const level = h[1].length;
      out.push(`<h${level}>${inline(h[2])}</h${level}>`);
      continue;
    }

    // Horizontal rule
    if (/^---+\s*$/.test(line) || /^\*\*\*+\s*$/.test(line)) {
      closeList();
      out.push("<hr />");
      continue;
    }

    // Blockquote
    if (line.startsWith("> ")) {
      closeList();
      out.push(`<blockquote>${inline(line.slice(2))}</blockquote>`);
      continue;
    }

    // Unordered list
    if (/^\s*[-*+]\s+/.test(line)) {
      if (inOl) {
        out.push("</ol>");
        inOl = false;
      }
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${inline(line.replace(/^\s*[-*+]\s+/, ""))}</li>`);
      continue;
    }

    // Ordered list
    if (/^\s*\d+\.\s+/.test(line)) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      if (!inOl) {
        out.push("<ol>");
        inOl = true;
      }
      out.push(`<li>${inline(line.replace(/^\s*\d+\.\s+/, ""))}</li>`);
      continue;
    }

    // Blank line
    if (line.trim() === "") {
      closeList();
      continue;
    }

    // Paragraph
    closeList();
    out.push(`<p>${inline(line)}</p>`);
  }

  closeList();
  if (inCode) {
    out.push(`<pre><code>${escapeHtml(codeBuf.join("\n"))}</code></pre>`);
  }
  return out.join("\n");
}

function inline(s: string): string {
  let r = escapeHtml(s);
  // inline code
  r = r.replace(/`([^`]+)`/g, "<code>$1</code>");
  // bold
  r = r.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  r = r.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  // italic
  r = r.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  r = r.replace(/_([^_]+)_/g, "<em>$1</em>");
  // links [text](url)
  r = r.replace(
    /\[([^\]]+)\]\(([^)\s]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );
  return r;
}
