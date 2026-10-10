"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getHealth, getKBStats, listDocuments } from "@/lib/api";

type Health = {
  status?: string;
  version?: string;
  services?: Record<string, string>;
  uptime_seconds?: number;
};

type KBStats = {
  vector_count?: number;
  chunk_count?: number;
  document_count?: number;
  embedding_dim?: number;
  index_type?: string;
};

type Docs = {
  total?: number;
  documents?: Array<{
    id: string;
    filename: string;
    content_type?: string;
    size?: number;
    created_at?: string;
    status?: string;
  }>;
};

function fmtNum(n?: number) {
  if (n == null) return "—";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "k";
  return String(n);
}

function fmtSize(bytes?: number) {
  if (!bytes) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let v = bytes;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

function timeAgo(iso?: string) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const sec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}

export default function Dashboard() {
  const [health, setHealth] = useState<Health | null>(null);
  const [stats, setStats] = useState<KBStats | null>(null);
  const [docs, setDocs] = useState<Docs | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [h, s, d] = await Promise.all([
          getHealth().catch(() => null),
          getKBStats().catch(() => null),
          listDocuments().catch(() => null),
        ]);
        if (cancelled) return;
        setHealth(h);
        setStats(s);
        setDocs(d);
      } catch (e: any) {
        setError(e?.message || "Failed to load dashboard data");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const isOk = health?.status === "ok" || health?.status === "healthy";
  const recentDocs = (docs?.documents || []).slice(0, 5);

  return (
    <div className="sov-fade-in">
      <PageHeader
        eyebrow="Overview"
        title="SOVEREIGN Workbench"
        description="On-premise agentic AI for confidential industrial work. Upload documents, ask grounded questions, run multi-step investigations, and export verified deliverables."
      />

      <div className="px-8 pb-12 space-y-8 max-w-[1400px] mx-auto">
        {/* Status cards */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <StatusCard
            label="System Status"
            loading={loading}
            ok={isOk}
            value={isOk ? "Operational" : health ? health.status || "Unknown" : "Offline"}
            sub={`Version ${health?.version || "—"}`}
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
              </svg>
            }
          />
          <StatusCard
            label="Knowledge Base"
            loading={loading}
            value={fmtNum(stats?.vector_count)}
            sub={`${fmtNum(stats?.chunk_count || stats?.document_count)} chunks · ${stats?.embedding_dim || "—"}d embeddings`}
            accent="primary"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
              </svg>
            }
          />
          <StatusCard
            label="Documents"
            loading={loading}
            value={String(docs?.total ?? "—")}
            sub={`${recentDocs.length} recent uploads`}
            accent="success"
            icon={
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                <path d="M14 3v4a1 1 0 0 0 1 1h4" />
                <path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z" />
              </svg>
            }
          />
        </section>

        {/* Quick actions */}
        <section className="sov-card p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-[15px] font-semibold text-white">Quick Actions</h2>
              <p className="text-[12.5px] text-zinc-500 mt-0.5">
                Jump straight into common workflows.
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <QuickAction
              href="/documents"
              label="Upload Document"
              hint="Add to KB"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <path d="M17 8l-5-5-5 5M12 3v12" />
                </svg>
              }
            />
            <QuickAction
              href="/search"
              label="Search KB"
              hint="Vector retrieval"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                  <circle cx="11" cy="11" r="7" />
                  <path d="m21 21-4.3-4.3" />
                </svg>
              }
            />
            <QuickAction
              href="/rag"
              label="Ask Question"
              hint="Grounded Q&A"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                  <path d="M8 10h.01M12 10h.01M16 10h.01" />
                </svg>
              }
            />
            <QuickAction
              href="/agents"
              label="Run Agent"
              hint="Multi-step task"
              icon={
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                  <rect x="4" y="6" width="16" height="12" rx="2" />
                  <path d="M12 2v2M9 2h6" />
                  <circle cx="9" cy="12" r="1.2" fill="currentColor" stroke="none" />
                  <circle cx="15" cy="12" r="1.2" fill="currentColor" stroke="none" />
                </svg>
              }
            />
          </div>
        </section>

        {/* Recent activity + Capabilities */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="sov-card p-6 lg:col-span-2">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-[15px] font-semibold text-white">Recent Activity</h2>
                <p className="text-[12.5px] text-zinc-500 mt-0.5">
                  Latest documents added to the knowledge base.
                </p>
              </div>
              <Link
                href="/documents"
                className="text-[12.5px] font-medium text-indigo-400 hover:text-indigo-300 transition-colors"
              >
                View all →
              </Link>
            </div>

            {loading ? (
              <div className="space-y-2.5">
                {[0, 1, 2, 3].map((i) => (
                  <div key={i} className="flex items-center gap-3">
                    <div className="sov-skeleton h-9 w-9 rounded-lg" />
                    <div className="flex-1 space-y-1.5">
                      <div className="sov-skeleton h-3.5 w-1/2" />
                      <div className="sov-skeleton h-3 w-1/4" />
                    </div>
                    <div className="sov-skeleton h-3 w-16" />
                  </div>
                ))}
              </div>
            ) : recentDocs.length === 0 ? (
              <EmptyState
                title="No documents yet"
                description="Upload your first document to start building the knowledge base."
                actionHref="/documents"
                actionLabel="Upload a document"
              />
            ) : (
              <ul className="space-y-1">
                {recentDocs.map((d) => (
                  <li
                    key={d.id}
                    className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-zinc-900/60 transition-colors"
                  >
                    <div
                      className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                      style={{
                        background: "var(--color-surface-2)",
                        border: "1px solid var(--color-border)",
                      }}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 text-zinc-400">
                        <path d="M14 3v4a1 1 0 0 0 1 1h4" />
                        <path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z" />
                      </svg>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-[13.5px] font-medium text-zinc-100 truncate">
                        {d.filename}
                      </div>
                      <div className="text-[11.5px] text-zinc-500 mt-0.5">
                        {d.content_type || "file"} · {fmtSize(d.size)}
                      </div>
                    </div>
                    <div className="text-[11.5px] text-zinc-500 shrink-0">
                      {timeAgo(d.created_at)}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="sov-card p-6">
            <h2 className="text-[15px] font-semibold text-white mb-1">Capabilities</h2>
            <p className="text-[12.5px] text-zinc-500 mb-4">
              What this workbench can do.
            </p>
            <ul className="space-y-3">
              <Capability
                title="Grounded Q&A"
                description="Answers cite source passages with support verdicts."
              />
              <Capability
                title="Agent Pipelines"
                description="Multi-step planning, retrieval, analysis, and synthesis."
              />
              <Capability
                title="Tamper-Evident Audit"
                description="Every action chained and verifiable on-premise."
              />
              <Capability
                title="Export Anywhere"
                description="PDF, DOCX, XLSX, CSV, JSON, Markdown deliverables."
              />
            </ul>
          </div>
        </section>
      </div>
    </div>
  );
}

/* ---------- Local UI helpers ---------- */

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
        background:
          "linear-gradient(180deg, rgba(99,102,241,0.04) 0%, transparent 100%)",
        borderColor: "var(--color-border)",
      }}
    >
      <div className="max-w-[1400px] mx-auto">
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

function StatusCard({
  label,
  value,
  sub,
  icon,
  loading,
  ok,
  accent = "neutral",
}: {
  label: string;
  value: string;
  sub: string;
  icon: React.ReactNode;
  loading?: boolean;
  ok?: boolean;
  accent?: "neutral" | "primary" | "success";
}) {
  const accentColor =
    accent === "primary"
      ? "var(--color-primary)"
      : accent === "success"
      ? "var(--color-success)"
      : "var(--color-text-muted)";

  return (
    <div className="sov-card sov-card-hover p-5">
      <div className="flex items-start justify-between">
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center"
          style={{
            background: "var(--color-surface-2)",
            border: "1px solid var(--color-border)",
            color: accentColor,
          }}
        >
          {icon}
        </div>
        {ok !== undefined && (
          <span className="sov-badge sov-badge-dot badge-supported">
            {ok ? "Online" : "Down"}
          </span>
        )}
      </div>
      <div className="mt-4">
        <div className="text-[11.5px] uppercase tracking-wider font-medium text-zinc-500">
          {label}
        </div>
        {loading ? (
          <div className="sov-skeleton h-7 w-32 mt-1.5" />
        ) : (
          <div className="text-[22px] font-semibold text-white mt-0.5 tracking-tight">
            {value}
          </div>
        )}
        <div className="text-[12px] text-zinc-500 mt-1">{loading ? "…" : sub}</div>
      </div>
    </div>
  );
}

function QuickAction({
  href,
  label,
  hint,
  icon,
}: {
  href: string;
  label: string;
  hint: string;
  icon: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="group flex flex-col items-start gap-3 p-4 rounded-lg border transition-all hover:-translate-y-0.5"
      style={{
        background: "var(--color-surface-2)",
        borderColor: "var(--color-border)",
      }}
    >
      <span
        className="w-9 h-9 rounded-lg flex items-center justify-center text-zinc-300 group-hover:text-white transition-colors"
        style={{
          background: "var(--color-surface-3)",
          border: "1px solid var(--color-border)",
        }}
      >
        {icon}
      </span>
      <div>
        <div className="text-[13.5px] font-medium text-zinc-100">{label}</div>
        <div className="text-[11.5px] text-zinc-500 mt-0.5">{hint}</div>
      </div>
    </Link>
  );
}

function Capability({ title, description }: { title: string; description: string }) {
  return (
    <li className="flex items-start gap-3">
      <span
        className="mt-0.5 w-5 h-5 rounded-full flex items-center justify-center shrink-0"
        style={{
          background: "rgba(16, 185, 129, 0.12)",
          color: "var(--color-success)",
          border: "1px solid rgba(16,185,129,0.3)",
        }}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="w-3 h-3">
          <path d="m5 12 5 5L20 7" />
        </svg>
      </span>
      <div>
        <div className="text-[13px] font-medium text-zinc-100">{title}</div>
        <div className="text-[12px] text-zinc-500 mt-0.5 leading-relaxed">
          {description}
        </div>
      </div>
    </li>
  );
}

function EmptyState({
  title,
  description,
  actionHref,
  actionLabel,
}: {
  title: string;
  description: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  return (
    <div className="sov-empty">
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center mb-3"
        style={{
          background: "var(--color-surface-2)",
          border: "1px solid var(--color-border)",
          color: "var(--color-text-subtle)",
        }}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6">
          <path d="M14 3v4a1 1 0 0 0 1 1h4" />
          <path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z" />
        </svg>
      </div>
      <div className="text-[14px] font-medium text-zinc-300">{title}</div>
      <div className="text-[12.5px] text-zinc-500 mt-1 max-w-sm">{description}</div>
      {actionHref && actionLabel && (
        <Link href={actionHref} className="sov-btn sov-btn-primary mt-4">
          {actionLabel}
        </Link>
      )}
    </div>
  );
}
