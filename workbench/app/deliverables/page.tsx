"use client";

import { useState } from "react";
import { createDeliverable, exportDeliverable } from "@/lib/api";

type DeliverableType = {
  id: string;
  label: string;
  description: string;
  icon: React.ReactNode;
};

type CreateResp = {
  title?: string;
  content?: string;
  markdown?: string;
  preview?: string;
  metadata?: any;
};

const TYPES: DeliverableType[] = [
  {
    id: "risk_assessment",
    label: "Risk Assessment",
    description: "Identify hazards, exposures, and mitigation actions.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
        <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
        <path d="M12 9v4M12 17h.01" />
      </svg>
    ),
  },
  {
    id: "incident_report",
    label: "Incident Report",
    description: "Structured post-incident analysis with timeline.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
        <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
        <path d="M12 9v4M12 17h.01" />
      </svg>
    ),
  },
  {
    id: "compliance_audit",
    label: "Compliance Audit",
    description: "Verify against requirements, surface gaps.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
    ),
  },
  {
    id: "executive_summary",
    label: "Executive Summary",
    description: "Concise briefing for leadership, key findings only.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6M8 13h8M8 17h5" />
      </svg>
    ),
  },
  {
    id: "technical_report",
    label: "Technical Report",
    description: "In-depth engineering analysis with citations.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
        <path d="M14 3v4a1 1 0 0 0 1 1h4" />
        <path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z" />
        <path d="M9 13h6M9 17h4" />
      </svg>
    ),
  },
  {
    id: "procedure",
    label: "Procedure",
    description: "Step-by-step SOP with safety callouts.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
    ),
  },
];

const FORMATS = [
  { id: "pdf", label: "PDF", color: "#ef4444" },
  { id: "docx", label: "DOCX", color: "#3b82f6" },
  { id: "xlsx", label: "XLSX", color: "#10b981" },
  { id: "csv", label: "CSV", color: "#f59e0b" },
  { id: "json", label: "JSON", color: "#a1a1aa" },
  { id: "md", label: "MD", color: "#6366f1" },
];

export default function DeliverablesPage() {
  const [type, setType] = useState<string>(TYPES[0].id);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState<string>("");
  const [markdown, setMarkdown] = useState<string>("");
  const [exporting, setExporting] = useState<string | null>(null);

  const generate = async () => {
    if (!query.trim() || loading) return;
    setLoading(true);
    setError(null);
    setMarkdown("");
    setTitle("");
    try {
      const resp: CreateResp = await createDeliverable({
        type,
        query,
      });
      const content =
        resp.content || resp.markdown || resp.preview || "";
      setMarkdown(content);
      setTitle(resp.title || TYPES.find((t) => t.id === type)?.label || "Deliverable");
    } catch (e: any) {
      setError(e?.message || "Failed to generate deliverable");
    } finally {
      setLoading(false);
    }
  };

  const doExport = async (format: string) => {
    if (!markdown) return;
    setExporting(format);
    try {
      const blob = await exportDeliverable({ type, query, content: markdown, title }, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(title || "deliverable").replace(/\s+/g, "_").toLowerCase()}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e?.message || `Export to ${format.toUpperCase()} failed`);
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="sov-fade-in">
      <PageHeader
        eyebrow="Intelligence"
        title="Deliverables"
        description="Generate structured, export-ready deliverables from your knowledge base. Pick a type, describe what you need, then export in any format."
      />

      <div className="px-8 pb-12 max-w-[1300px] mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-6">
          {/* Left: config */}
          <div className="space-y-5">
            {/* Type selector */}
            <section className="sov-card p-5">
              <label className="eyebrow block mb-3">Deliverable Type</label>
              <div className="grid grid-cols-1 gap-1.5">
                {TYPES.map((t) => {
                  const active = type === t.id;
                  return (
                    <button
                      key={t.id}
                      onClick={() => setType(t.id)}
                      className="flex items-start gap-3 p-3 rounded-lg text-left transition-all"
                      style={{
                        background: active
                          ? "linear-gradient(180deg, rgba(99,102,241,0.14), rgba(99,102,241,0.06))"
                          : "var(--color-surface-2)",
                        border: `1px solid ${
                          active ? "rgba(99,102,241,0.4)" : "var(--color-border)"
                        }`,
                      }}
                    >
                      <span
                        className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 transition-colors"
                        style={{
                          background: active
                            ? "rgba(99,102,241,0.18)"
                            : "var(--color-surface-3)",
                          color: active ? "var(--color-primary)" : "var(--color-text-muted)",
                          border: `1px solid ${active ? "rgba(99,102,241,0.4)" : "var(--color-border)"}`,
                        }}
                      >
                        {t.icon}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div
                          className="text-[13.5px] font-medium"
                          style={{ color: active ? "#fff" : "var(--color-text)" }}
                        >
                          {t.label}
                        </div>
                        <div className="text-[11.5px] text-zinc-500 mt-0.5 leading-relaxed">
                          {t.description}
                        </div>
                      </div>
                      {active && (
                        <svg viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 shrink-0 mt-1">
                          <path d="m5 12 5 5L20 7" />
                        </svg>
                      )}
                    </button>
                  );
                })}
              </div>
            </section>

            {/* Query */}
            <section className="sov-card p-5">
              <label className="eyebrow block mb-2">Query</label>
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. Generate a risk assessment for the new high-pressure boiler installation, focusing on commissioning and operating hazards."
                className="sov-input"
                rows={5}
              />
              <button
                onClick={generate}
                disabled={loading || !query.trim()}
                className="sov-btn sov-btn-primary w-full mt-3"
                style={{ height: 42 }}
              >
                {loading ? <span className="sov-spinner" /> : null}
                {loading ? "Generating…" : "Generate Deliverable"}
              </button>
              {error && (
                <div
                  className="mt-3 p-3 rounded-lg flex items-start gap-2"
                  style={{
                    background: "rgba(239, 68, 68, 0.06)",
                    border: "1px solid rgba(239, 68, 68, 0.3)",
                  }}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="var(--color-danger)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 shrink-0 mt-0.5">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 8v4M12 16h.01" />
                  </svg>
                  <div className="text-[12px] text-red-300">{error}</div>
                </div>
              )}
            </section>

            {/* Export */}
            {markdown && (
              <section className="sov-card p-5 sov-fade-in">
                <label className="eyebrow block mb-3">Export</label>
                <div className="grid grid-cols-3 gap-2">
                  {FORMATS.map((f) => (
                    <button
                      key={f.id}
                      onClick={() => doExport(f.id)}
                      disabled={exporting !== null}
                      className="sov-btn sov-btn-secondary flex-col py-2.5 gap-1.5"
                      style={{ height: "auto" }}
                    >
                      {exporting === f.id ? (
                        <span className="sov-spinner" style={{ width: 14, height: 14 }} />
                      ) : (
                        <span
                          className="w-7 h-7 rounded-md flex items-center justify-center text-[10px] font-bold"
                          style={{
                            background: `${f.color}22`,
                            color: f.color,
                            border: `1px solid ${f.color}44`,
                          }}
                        >
                          {f.label.slice(0, 1)}
                        </span>
                      )}
                      <span className="text-[12px] font-medium">{f.label}</span>
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-zinc-600 mt-3">
                  Downloads immediately to your device.
                </p>
              </section>
            )}
          </div>

          {/* Right: preview */}
          <section className="sov-card overflow-hidden flex flex-col min-h-[640px]">
            <div
              className="px-5 py-4 border-b flex items-center justify-between"
              style={{ borderColor: "var(--color-border)" }}
            >
              <div className="min-w-0">
                <div className="text-[11px] uppercase tracking-wider font-semibold text-zinc-500">
                  Preview
                </div>
                <div className="text-[14px] font-semibold text-white truncate mt-0.5">
                  {title || "No deliverable yet"}
                </div>
              </div>
              {markdown && (
                <span className="sov-badge badge-neutral">Markdown</span>
              )}
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              {loading ? (
                <PreviewSkeleton />
              ) : markdown ? (
                <div className="sov-prose">
                  <MarkdownPreview content={markdown} />
                </div>
              ) : (
                <EmptyPreview />
              )}
            </div>
          </section>
        </div>
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
      <div className="max-w-[1300px] mx-auto">
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

function EmptyPreview() {
  return (
    <div className="sov-empty h-full min-h-[480px]">
      <div
        className="w-14 h-14 rounded-2xl flex items-center justify-center mb-3"
        style={{
          background: "var(--color-surface-2)",
          border: "1px solid var(--color-border)",
          color: "var(--color-text-subtle)",
        }}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="w-7 h-7">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <path d="M14 2v6h6M9 13h6M9 17h4" />
        </svg>
      </div>
      <div className="text-[14px] font-medium text-zinc-300">No deliverable generated</div>
      <div className="text-[12.5px] text-zinc-500 mt-1 max-w-sm">
        Pick a type, write a query, and hit generate to see a markdown preview here.
      </div>
    </div>
  );
}

function PreviewSkeleton() {
  return (
    <div className="space-y-3">
      <div className="sov-skeleton h-7 w-2/3" />
      <div className="space-y-2">
        <div className="sov-skeleton h-3 w-full" />
        <div className="sov-skeleton h-3 w-5/6" />
        <div className="sov-skeleton h-3 w-3/4" />
      </div>
      <div className="sov-skeleton h-5 w-1/3 mt-4" />
      <div className="space-y-2">
        <div className="sov-skeleton h-3 w-full" />
        <div className="sov-skeleton h-3 w-4/5" />
        <div className="sov-skeleton h-3 w-2/3" />
      </div>
      <div className="sov-skeleton h-5 w-1/4 mt-4" />
      <div className="space-y-2">
        <div className="sov-skeleton h-3 w-full" />
        <div className="sov-skeleton h-3 w-5/6" />
      </div>
    </div>
  );
}

function MarkdownPreview({ content }: { content: string }) {
  const html = renderMarkdown(content);
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}

function escapeHtml(s: string) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
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

    const h = /^(#{1,6})\s+(.*)$/.exec(line);
    if (h) {
      closeList();
      const level = h[1].length;
      out.push(`<h${level}>${inline(h[2])}</h${level}>`);
      continue;
    }

    if (/^---+\s*$/.test(line) || /^\*\*\*+\s*$/.test(line)) {
      closeList();
      out.push("<hr />");
      continue;
    }

    if (line.startsWith("> ")) {
      closeList();
      out.push(`<blockquote>${inline(line.slice(2))}</blockquote>`);
      continue;
    }

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

    if (line.trim() === "") {
      closeList();
      continue;
    }

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
  r = r.replace(/`([^`]+)`/g, "<code>$1</code>");
  r = r.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  r = r.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  r = r.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  r = r.replace(/_([^_]+)_/g, "<em>$1</em>");
  r = r.replace(
    /\[([^\]]+)\]\(([^)\s]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );
  return r;
}
