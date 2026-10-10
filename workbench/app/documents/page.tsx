"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  listDocuments,
  uploadDocument,
  deleteDocument,
} from "@/lib/api";

type Doc = {
  id: string;
  filename: string;
  content_type?: string;
  size?: number;
  created_at?: string;
  status?: string;
  chunks?: number;
};

type DocsResp = {
  total?: number;
  documents?: Doc[];
};

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

function fileIcon(type?: string) {
  if (type?.includes("pdf")) return "PDF";
  if (type?.includes("word") || type?.includes("doc")) return "DOC";
  if (type?.includes("sheet") || type?.includes("excel") || type?.includes("csv")) return "XLS";
  if (type?.includes("text") || type?.includes("markdown")) return "TXT";
  if (type?.includes("html")) return "HTML";
  return "FILE";
}

type UploadState = {
  filename: string;
  status: "uploading" | "done" | "error";
  error?: string;
};

export default function DocumentsPage() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploads, setUploads] = useState<UploadState[]>([]);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp: DocsResp = await listDocuments();
      setDocs(resp?.documents || []);
      setTotal(resp?.total ?? (resp?.documents?.length || 0));
    } catch (e: any) {
      setError(e?.message || "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const list = Array.from(files);
      for (const f of list) {
        const id = crypto.randomUUID();
        setUploads((u) => [
          { filename: f.name, status: "uploading" },
          ...u,
        ]);
        try {
          await uploadDocument(f);
          setUploads((u) =>
            u.map((x) =>
              x.filename === f.name && x.status === "uploading"
                ? { ...x, status: "done" }
                : x
            )
          );
        } catch (e: any) {
          setUploads((u) =>
            u.map((x) =>
              x.filename === f.name && x.status === "uploading"
                ? { ...x, status: "error", error: e?.message || "Upload failed" }
                : x
            )
          );
        }
      }
      // Refresh doc list after uploads finish
      setTimeout(() => load(), 400);
      // Clear completed uploads after a delay
      setTimeout(() => {
        setUploads((u) => u.filter((x) => x.status !== "done"));
      }, 3500);
    },
    [load]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles]
  );

  const onDelete = useCallback(
    async (id: string) => {
      setDeletingId(id);
      try {
        await deleteDocument(id);
        setDocs((d) => d.filter((x) => x.id !== id));
        setTotal((t) => Math.max(0, t - 1));
      } catch {
        // ignore
      } finally {
        setDeletingId(null);
      }
    },
    []
  );

  const totalSize = docs.reduce((sum, d) => sum + (d.size || 0), 0);

  return (
    <div className="sov-fade-in">
      <PageHeader
        eyebrow="Workspace"
        title="Documents"
        description="Upload files to build your private knowledge base. Documents are chunked, embedded, and indexed on-premise."
      />

      <div className="px-8 pb-12 space-y-6 max-w-[1400px] mx-auto">
        {/* Dropzone */}
        <section
          className={`sov-dropzone p-8 ${dragOver ? "sov-dropzone-dragging" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
            accept=".pdf,.doc,.docx,.txt,.md,.csv,.xlsx,.xls,.html,.json"
          />
          <div className="flex flex-col items-center text-center">
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4 transition-transform"
              style={{
                background:
                  "linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(99,102,241,0.05) 100%)",
                border: "1px solid rgba(99,102,241,0.3)",
                color: "var(--color-primary)",
                transform: dragOver ? "scale(1.08)" : "scale(1)",
              }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-7 h-7">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <path d="M17 8l-5-5-5 5M12 3v12" />
              </svg>
            </div>
            <h3 className="text-[15px] font-semibold text-white">
              Drop files here, or{" "}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="text-indigo-400 hover:text-indigo-300 underline underline-offset-2 font-medium"
              >
                browse
              </button>
            </h3>
            <p className="text-[12.5px] text-zinc-500 mt-1.5 max-w-md">
              Supports PDF, DOC/DOCX, TXT, MD, CSV, XLSX, HTML, JSON up to your server limit.
            </p>
          </div>
        </section>

        {/* Upload progress */}
        {uploads.length > 0 && (
          <section className="space-y-2">
            {uploads.map((u, i) => (
              <div
                key={i}
                className="sov-card p-3 flex items-center gap-3 sov-fade-in"
              >
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                  style={{
                    background: "var(--color-surface-2)",
                    border: "1px solid var(--color-border)",
                  }}
                >
                  {u.status === "uploading" ? (
                    <span className="sov-spinner" />
                  ) : u.status === "done" ? (
                    <svg viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                      <path d="m5 12 5 5L20 7" />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" fill="none" stroke="var(--color-danger)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                      <path d="M18 6 6 18M6 6l12 12" />
                    </svg>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium text-zinc-100 truncate">
                    {u.filename}
                  </div>
                  <div className="text-[11.5px] text-zinc-500 mt-0.5">
                    {u.status === "uploading" && "Uploading & indexing…"}
                    {u.status === "done" && "Upload complete"}
                    {u.status === "error" && (u.error || "Upload failed")}
                  </div>
                </div>
                {u.status === "uploading" && (
                  <div className="flex-1 max-w-[160px] h-1 rounded-full overflow-hidden" style={{ background: "var(--color-surface-2)" }}>
                    <div
                      className="h-full rounded-full"
                      style={{
                        background: "linear-gradient(90deg, #6366f1, #818cf8)",
                        width: "60%",
                        animation: "shimmer 1.4s ease-in-out infinite",
                      }}
                    />
                  </div>
                )}
              </div>
            ))}
          </section>
        )}

        {/* Document table */}
        <section className="sov-card overflow-hidden">
          <div className="flex items-center justify-between p-5 border-b" style={{ borderColor: "var(--color-border)" }}>
            <div>
              <h2 className="text-[15px] font-semibold text-white">
                Document Library
              </h2>
              <p className="text-[12.5px] text-zinc-500 mt-0.5">
                {total} document{total === 1 ? "" : "s"} · {fmtSize(totalSize)} total
              </p>
            </div>
            <button onClick={load} className="sov-btn sov-btn-ghost">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
                <path d="M21 3v5h-5" />
              </svg>
              Refresh
            </button>
          </div>

          {error ? (
            <div className="p-6">
              <ErrorBanner message={error} onRetry={load} />
            </div>
          ) : loading ? (
            <TableSkeleton />
          ) : docs.length === 0 ? (
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
              <div className="text-[14px] font-medium text-zinc-300">No documents</div>
              <div className="text-[12.5px] text-zinc-500 mt-1 max-w-sm">
                Drop a file above or browse to upload your first document.
              </div>
            </div>
          ) : (
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
                    <th className="px-5 py-3 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">Name</th>
                    <th className="px-3 py-3 text-[11px] font-semibold uppercase tracking-wider text-zinc-500 w-20">Type</th>
                    <th className="px-3 py-3 text-[11px] font-semibold uppercase tracking-wider text-zinc-500 w-24">Size</th>
                    <th className="px-3 py-3 text-[11px] font-semibold uppercase tracking-wider text-zinc-500 w-24">Status</th>
                    <th className="px-3 py-3 text-[11px] font-semibold uppercase tracking-wider text-zinc-500 w-28">Uploaded</th>
                    <th className="px-5 py-3 w-12" />
                  </tr>
                </thead>
                <tbody>
                  {docs.map((d) => (
                    <tr
                      key={d.id}
                      className="border-b last:border-0 hover:bg-zinc-900/40 transition-colors group"
                      style={{ borderColor: "var(--color-border)" }}
                    >
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-3 min-w-0">
                          <div
                            className="w-8 h-8 rounded-md flex items-center justify-center shrink-0 text-[9px] font-bold tracking-tight"
                            style={{
                              background: "var(--color-surface-2)",
                              border: "1px solid var(--color-border)",
                              color: "var(--color-text-muted)",
                            }}
                          >
                            {fileIcon(d.content_type)}
                          </div>
                          <div className="min-w-0">
                            <div className="text-[13px] font-medium text-zinc-100 truncate max-w-[420px]">
                              {d.filename}
                            </div>
                            <div className="text-[11px] text-zinc-500 truncate font-mono">
                              {d.id.slice(0, 12)}…
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-3 text-[12px] text-zinc-400 font-mono">
                        {d.content_type?.split("/")[1] || "file"}
                      </td>
                      <td className="px-3 py-3 text-[12px] text-zinc-400">
                        {fmtSize(d.size)}
                      </td>
                      <td className="px-3 py-3">
                        <span className="sov-badge sov-badge-dot badge-supported">
                          {d.status || "indexed"}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-[12px] text-zinc-500">
                        {timeAgo(d.created_at)}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <button
                          onClick={() => onDelete(d.id)}
                          disabled={deletingId === d.id}
                          className="p-1.5 rounded-md text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition-colors opacity-0 group-hover:opacity-100"
                          title="Delete document"
                          aria-label="Delete document"
                        >
                          {deletingId === d.id ? (
                            <span className="sov-spinner" style={{ width: 14, height: 14 }} />
                          ) : (
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                              <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                              <path d="M10 11v6M14 11v6" />
                            </svg>
                          )}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
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

function TableSkeleton() {
  return (
    <div className="p-5 space-y-2.5">
      {[0, 1, 2, 3, 4].map((i) => (
        <div key={i} className="flex items-center gap-3">
          <div className="sov-skeleton h-9 w-9 rounded-md" />
          <div className="flex-1 space-y-1.5">
            <div className="sov-skeleton h-3.5 w-1/3" />
            <div className="sov-skeleton h-3 w-1/4" />
          </div>
          <div className="sov-skeleton h-3 w-12" />
          <div className="sov-skeleton h-5 w-16 rounded-full" />
          <div className="sov-skeleton h-3 w-20" />
        </div>
      ))}
    </div>
  );
}

function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
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
        <div className="text-[13px] font-medium text-red-300">Something went wrong</div>
        <div className="text-[12px] text-red-400/80 mt-0.5">{message}</div>
      </div>
      {onRetry && (
        <button onClick={onRetry} className="sov-btn sov-btn-secondary">
          Retry
        </button>
      )}
    </div>
  );
}
