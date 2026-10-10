"use client";

import { useState } from "react";
import { search } from "@/lib/api";

type SearchResult = {
  id?: string;
  document_id?: string;
  filename?: string;
  content?: string;
  text?: string;
  score?: number;
  section?: string;
  section_path?: string;
  page?: number;
  chunk_index?: number;
  metadata?: Record<string, any>;
};

type SearchResp = {
  results?: SearchResult[];
  query?: string;
  total?: number;
  took_ms?: number;
};

function scoreColor(s?: number) {
  if (s == null) return "badge-neutral";
  if (s >= 0.85) return "badge-supported";
  if (s >= 0.7) return "badge-partial";
  if (s >= 0.5) return "badge-conflicting";
  return "badge-unsupported";
}

function scoreLabel(s?: number) {
  if (s == null) return "—";
  if (s >= 0.85) return "Excellent";
  if (s >= 0.7) return "Good";
  if (s >= 0.5) return "Moderate";
  return "Weak";
}

function highlight(text: string, query: string) {
  if (!query.trim()) return text;
  const terms = query
    .split(/\s+/)
    .filter((t) => t.length > 2)
    .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (terms.length === 0) return text;
  const re = new RegExp(`(${terms.join("|")})`, "gi");
  const parts = text.split(re);
  return parts.map((p, i) =>
    re.test(p) ? (
      <mark
        key={i}
        style={{
          background: "rgba(99,102,241,0.25)",
          color: "#c7c9fb",
          borderRadius: 3,
          padding: "0 2px",
        }}
      >
        {p}
      </mark>
    ) : (
      <span key={i}>{p}</span>
    )
  );
}

const EXAMPLES = [
  "safety procedure for high-pressure systems",
  "incident response protocol",
  "supplier compliance requirements",
  "warranty claim process",
];

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(8);
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tookMs, setTookMs] = useState<number | null>(null);
  const [total, setTotal] = useState<number | null>(null);

  const run = async (q?: string) => {
    const finalQuery = (q ?? query).trim();
    if (!finalQuery) return;
    if (q) setQuery(q);
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const resp: SearchResp = await search({ query: finalQuery, top_k: topK });
      setResults(resp?.results || []);
      setTookMs(resp?.took_ms ?? null);
      setTotal(resp?.total ?? resp?.results?.length ?? 0);
    } catch (e: any) {
      setError(e?.message || "Search failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="sov-fade-in">
      <PageHeader
        eyebrow="Intelligence"
        title="Search"
        description="Vector search across your knowledge base. Returns the most semantically similar passages with relevance scores."
      />

      <div className="px-8 pb-12 max-w-[1100px] mx-auto space-y-6">
        {/* Search bar */}
        <section className="sov-card p-4">
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500">
                <circle cx="11" cy="11" r="7" />
                <path d="m21 21-4.3-4.3" />
              </svg>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && run()}
                placeholder="Search for concepts, procedures, requirements…"
                className="sov-input pl-10"
                style={{ height: 42 }}
              />
            </div>
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="sov-input"
              style={{ width: 110, height: 42 }}
              title="Number of results"
            >
              <option value={5}>Top 5</option>
              <option value={8}>Top 8</option>
              <option value={12}>Top 12</option>
              <option value={20}>Top 20</option>
            </select>
            <button
              onClick={() => run()}
              disabled={loading || !query.trim()}
              className="sov-btn sov-btn-primary"
              style={{ height: 42 }}
            >
              {loading ? <span className="sov-spinner" /> : null}
              {loading ? "Searching…" : "Search"}
            </button>
          </div>

          {/* Examples */}
          {!results && !loading && (
            <div className="flex items-center gap-2 mt-3 flex-wrap">
              <span className="text-[11.5px] text-zinc-500">Try:</span>
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => run(ex)}
                  className="text-[12px] px-2.5 py-1 rounded-full border transition-colors hover:border-indigo-500/50 hover:text-indigo-300"
                  style={{
                    background: "var(--color-surface-2)",
                    borderColor: "var(--color-border)",
                    color: "var(--color-text-muted)",
                  }}
                >
                  {ex}
                </button>
              ))}
            </div>
          )}
        </section>

        {/* Meta */}
        {results && !loading && !error && (
          <div className="flex items-center justify-between text-[12.5px] text-zinc-500">
            <span>
              <span className="text-zinc-300 font-medium">{total ?? results.length}</span>{" "}
              result{results.length === 1 ? "" : "s"}
              {tookMs != null && (
                <>
                  {" "}· <span className="text-zinc-400">{tookMs.toFixed(0)}ms</span>
                </>
              )}
            </span>
            <button
              onClick={() => {
                setResults(null);
                setQuery("");
              }}
              className="text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              Clear
            </button>
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className="space-y-3">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="sov-card p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="sov-skeleton h-4 w-32" />
                  <div className="sov-skeleton h-5 w-16 rounded-full" />
                </div>
                <div className="space-y-2">
                  <div className="sov-skeleton h-3 w-full" />
                  <div className="sov-skeleton h-3 w-5/6" />
                  <div className="sov-skeleton h-3 w-2/3" />
                </div>
              </div>
            ))}
          </div>
        )}

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
              <div className="text-[13px] font-medium text-red-300">Search failed</div>
              <div className="text-[12px] text-red-400/80 mt-0.5">{error}</div>
            </div>
          </div>
        )}

        {/* Results */}
        {results && !loading && !error && (
          <>
            {results.length === 0 ? (
              <div className="sov-card sov-empty">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center mb-3"
                  style={{
                    background: "var(--color-surface-2)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text-subtle)",
                  }}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6">
                    <circle cx="11" cy="11" r="7" />
                    <path d="m21 21-4.3-4.3" />
                  </svg>
                </div>
                <div className="text-[14px] font-medium text-zinc-300">No matches found</div>
                <div className="text-[12.5px] text-zinc-500 mt-1 max-w-sm">
                  Try different phrasing or check that documents have been uploaded to the KB.
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {results.map((r, i) => {
                  const content = r.content || r.text || "";
                  const sectionPath =
                    r.section_path || r.section || r.metadata?.section_path;
                  return (
                    <article
                      key={r.id || i}
                      className="sov-card sov-card-hover p-5 sov-fade-in"
                    >
                      <div className="flex items-start justify-between gap-3 mb-3">
                        <div className="flex items-center gap-2 min-w-0 flex-wrap">
                          <span className="text-[11px] text-zinc-500 font-mono">
                            #{i + 1}
                          </span>
                          {r.filename && (
                            <span className="sov-badge badge-primary">
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-3 h-3">
                                <path d="M14 3v4a1 1 0 0 0 1 1h4" />
                                <path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z" />
                              </svg>
                              {r.filename}
                            </span>
                          )}
                          {sectionPath && (
                            <span className="text-[11.5px] text-zinc-500 font-mono truncate">
                              {sectionPath}
                            </span>
                          )}
                          {r.page != null && (
                            <span className="text-[11px] text-zinc-600">
                              p.{r.page}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className={`sov-badge ${scoreColor(r.score)}`}>
                            {scoreLabel(r.score)}
                          </span>
                          <span className="text-[12px] font-mono font-semibold text-zinc-300 tabular-nums">
                            {r.score != null ? r.score.toFixed(3) : "—"}
                          </span>
                        </div>
                      </div>
                      <p className="text-[13.5px] leading-relaxed text-zinc-300">
                        "{highlight(content.slice(0, 400), query)}
                        {content.length > 400 ? "…" : ""}"
                      </p>
                      {r.document_id && (
                        <div className="mt-3 flex items-center gap-2 text-[11px] text-zinc-600 font-mono">
                          <span className="text-zinc-500">doc:</span>
                          <span className="truncate">{r.document_id}</span>
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            )}
          </>
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
      <div className="max-w-[1100px] mx-auto">
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
