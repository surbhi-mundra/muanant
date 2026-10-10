"use client";

import { useEffect, useRef, useState } from "react";
import { ragQuery } from "@/lib/api";

type Evidence = {
  text?: string;
  content?: string;
  document_id?: string;
  filename?: string;
  section?: string;
  section_path?: string;
  page?: number;
  chunk_index?: number;
  score?: number;
};

type Claim = {
  text?: string;
  statement?: string;
  support_status?: "supported" | "partial" | "unsupported" | "conflicting";
  evidence_indices?: number[];
  evidence?: Evidence[];
  confidence?: number;
};

type RagAnswer = {
  answer?: string;
  text?: string;
  verdict?: string;
  verdict_status?: "supported" | "partial" | "unsupported" | "conflicting";
  confidence?: number;
  claims?: Claim[];
  evidence?: Evidence[];
  sources?: Evidence[];
  metadata?: any;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  query?: string;
  answer?: RagAnswer;
  pending?: boolean;
  error?: string;
};

const SUGGESTED = [
  "What is the procedure for handling pressure vessel failures?",
  "Summarize our supplier qualification requirements.",
  "What are the warranty terms for industrial pumps?",
  "Explain the incident escalation matrix.",
];

function verdictBadge(status?: string) {
  const s = (status || "").toLowerCase();
  switch (s) {
    case "answered":
    case "supported":
      return { cls: "badge-supported", label: "ANSWERED" };
    case "insufficient_evidence":
    case "unsupported":
      return { cls: "badge-unsupported", label: "INSUFFICIENT EVIDENCE" };
    case "partial":
    case "partially_supported":
      return { cls: "badge-partial", label: "PARTIALLY SUPPORTED" };
    case "conflicting":
      return { cls: "badge-conflicting", label: "CONFLICTING" };
    case "out_of_scope":
      return { cls: "badge-unsupported", label: "OUT OF SCOPE" };
    default:
      return { cls: "badge-info", label: s ? s.toUpperCase() : "INFO" };
  }
}

export default function RagPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const ask = async (q?: string) => {
    const finalQuery = (q ?? input).trim();
    if (!finalQuery || loading) return;
    if (q) setInput(q);

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      query: finalQuery,
    };
    const pendingId = crypto.randomUUID();
    const pendingMsg: Message = {
      id: pendingId,
      role: "assistant",
      pending: true,
    };

    setMessages((m) => [...m, userMsg, pendingMsg]);
    setInput("");
    setLoading(true);

    try {
      const resp: RagAnswer = await ragQuery({ query: finalQuery });
      setMessages((m) =>
        m.map((msg) =>
          msg.id === pendingId
            ? { ...msg, pending: false, answer: resp }
            : msg
        )
      );
    } catch (e: any) {
      setMessages((m) =>
        m.map((msg) =>
          msg.id === pendingId
            ? { ...msg, pending: false, error: e?.message || "Query failed" }
            : msg
        )
      );
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      ask();
    }
  };

  return (
    <div className="sov-fade-in flex flex-col h-screen">
      <PageHeader
        eyebrow="Intelligence"
        title="Ask"
        description="Ask grounded questions against your knowledge base. Every answer includes a verdict, claim-level support status, and source citations."
      />

      <div className="flex-1 min-h-0 flex flex-col max-w-[1100px] mx-auto w-full px-8 pb-6">
        {/* Messages scroll area */}
        <div
          ref={scrollRef}
          className="sov-scroll-y flex-1 min-h-0 space-y-6 pr-1"
        >
          {messages.length === 0 ? (
            <WelcomeScreen onPick={ask} />
          ) : (
            messages.map((m) =>
              m.role === "user" ? (
                <UserMessage key={m.id} message={m} />
              ) : (
                <AssistantMessage key={m.id} message={m} />
              )
            )
          )}
        </div>

        {/* Input */}
        <div className="mt-4 shrink-0">
          <div
            className="sov-card p-2 flex items-end gap-2"
            style={{ borderColor: "var(--color-border-strong)" }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question about your documents…"
              rows={1}
              className="flex-1 bg-transparent border-0 outline-none resize-none px-3 py-2.5 text-[14px] text-zinc-100 placeholder:text-zinc-600 max-h-[160px]"
              style={{ minHeight: 42 }}
              disabled={loading}
            />
            <button
              onClick={() => ask()}
              disabled={loading || !input.trim()}
              className="sov-btn sov-btn-primary"
              style={{ height: 42 }}
            >
              {loading ? <span className="sov-spinner" /> : null}
              {loading ? "Thinking…" : "Ask"}
            </button>
          </div>
          <p className="text-[11px] text-zinc-600 mt-2 px-1">
            Press <kbd className="font-mono text-zinc-400">Enter</kbd> to send,{" "}
            <kbd className="font-mono text-zinc-400">Shift+Enter</kbd> for a new line.
          </p>
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
      className="px-8 pt-8 pb-6 border-b mb-6 sov-grid-bg shrink-0"
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

function WelcomeScreen({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center py-12">
      <div
        className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5"
        style={{
          background: "linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(99,102,241,0.05) 100%)",
          border: "1px solid rgba(99,102,241,0.3)",
          color: "var(--color-primary)",
        }}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="w-8 h-8">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          <path d="M8 10h.01M12 10h.01M16 10h.01" />
        </svg>
      </div>
      <h2 className="text-[18px] font-semibold text-white">Ask anything</h2>
      <p className="text-[13px] text-zinc-500 mt-1.5 max-w-md">
        Your question will be answered using grounded retrieval from the knowledge base,
        with claim-by-claim verification.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mt-7 max-w-2xl w-full">
        {SUGGESTED.map((s) => (
          <button
            key={s}
            onClick={() => onPick(s)}
            className="sov-card sov-card-hover p-4 text-left"
          >
            <div className="text-[13px] font-medium text-zinc-200">{s}</div>
            <div className="text-[11.5px] text-zinc-500 mt-1">Click to ask →</div>
          </button>
        ))}
      </div>
    </div>
  );
}

function UserMessage({ message }: { message: Message }) {
  return (
    <div className="flex justify-end sov-fade-in">
      <div
        className="max-w-[80%] rounded-2xl rounded-tr-sm px-4 py-3 text-[13.5px] text-white"
        style={{
          background: "linear-gradient(180deg, #6366f1 0%, #4f46e5 100%)",
          boxShadow: "0 4px 12px -4px rgba(99,102,241,0.4)",
        }}
      >
        {message.query}
      </div>
    </div>
  );
}

function AssistantMessage({ message }: { message: Message }) {
  if (message.pending) {
    return (
      <div className="flex gap-3 sov-fade-in">
        <Avatar />
        <div className="sov-card p-4 flex-1">
          <div className="flex items-center gap-2 mb-3">
            <span className="sov-spinner" />
            <span className="text-[13px] text-zinc-400">Retrieving & reasoning…</span>
          </div>
          <div className="space-y-2">
            <div className="sov-skeleton h-3 w-full" />
            <div className="sov-skeleton h-3 w-5/6" />
            <div className="sov-skeleton h-3 w-2/3" />
          </div>
        </div>
      </div>
    );
  }

  if (message.error) {
    return (
      <div className="flex gap-3 sov-fade-in">
        <Avatar />
        <div
          className="flex-1 p-4 rounded-lg flex items-start gap-3"
          style={{
            background: "rgba(239, 68, 68, 0.06)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
          }}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="var(--color-danger)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5 shrink-0 mt-0.5">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" />
          </svg>
          <div>
            <div className="text-[13px] font-medium text-red-300">Query failed</div>
            <div className="text-[12px] text-red-400/80 mt-0.5">{message.error}</div>
          </div>
        </div>
      </div>
    );
  }

  const answer = message.answer || {};
  const verdict = verdictBadge(answer.verdict);
  const answerText = answer.answer || "";
  const claims = answer.claims || [];
  const evidence = answer.evidence || [];
  const isAnswered = answer.is_answered;

  return (
    <div className="flex gap-3 sov-fade-in">
      <Avatar />
      <div className="flex-1 min-w-0 space-y-4">
        {/* Verdict banner */}
        <div className="sov-card p-4">
          <div className="flex items-center justify-between gap-3 mb-3">
            <div className="flex items-center gap-2">
              <span className="text-[11px] uppercase tracking-wider font-semibold text-zinc-500">
                Verdict
              </span>
              <span className={`sov-badge ${verdict.cls}`}>{verdict.label}</span>
            </div>
          </div>
          <p className="text-[14px] leading-relaxed text-zinc-100">{answerText}</p>
        </div>

        {/* Claims */}
        {claims.length > 0 && (
          <div className="sov-card p-4">
            <h3 className="text-[12px] uppercase tracking-wider font-semibold text-zinc-500 mb-3">
              Claim Verification
            </h3>
            <ul className="space-y-2.5">
              {claims.map((c, i) => {
                const v = verdictBadge(c.support_status);
                const text = c.text || c.statement || "";
                return (
                  <li
                    key={i}
                    className="flex items-start gap-3 p-3 rounded-lg"
                    style={{
                      background: "var(--color-surface-2)",
                      border: "1px solid var(--color-border)",
                    }}
                  >
                    <span className="text-[11px] font-mono text-zinc-500 mt-0.5 shrink-0">
                      C{i + 1}
                    </span>
                    <p className="flex-1 text-[13px] leading-relaxed text-zinc-200">
                      {text}
                    </p>
                    <span className={`sov-badge ${v.cls} shrink-0`}>{v.label}</span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {/* Evidence */}
        {evidence.length > 0 && (
          <div className="sov-card p-4">
            <h3 className="text-[12px] uppercase tracking-wider font-semibold text-zinc-500 mb-3">
              Evidence & Citations
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
              {evidence.map((ev, i) => {
                const text = ev.text || ev.content || "";
                const sectionPath = ev.section_path || ev.section;
                return (
                  <div
                    key={i}
                    className="p-3 rounded-lg"
                    style={{
                      background: "var(--color-surface-2)",
                      border: "1px solid var(--color-border)",
                    }}
                  >
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span
                        className="w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold text-indigo-300 shrink-0"
                        style={{
                          background: "rgba(99,102,241,0.12)",
                          border: "1px solid rgba(99,102,241,0.3)",
                        }}
                      >
                        {i + 1}
                      </span>
                      {ev.filename && (
                        <span className="sov-badge badge-primary text-[10px] py-0.5">
                          {ev.filename}
                        </span>
                      )}
                      {sectionPath && (
                        <span className="text-[10.5px] text-zinc-500 font-mono truncate">
                          {sectionPath}
                        </span>
                      )}
                    </div>
                    <p className="text-[12px] leading-relaxed text-zinc-400 italic line-clamp-4">
                      "{text.slice(0, 280)}
                      {text.length > 280 ? "…" : ""}"
                    </p>
                    {ev.score != null && (
                      <div className="mt-2 flex items-center gap-1.5">
                        <span className="text-[10px] text-zinc-600">relevance</span>
                        <span className="text-[11px] font-mono text-zinc-400">
                          {ev.score.toFixed(3)}
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Avatar() {
  return (
    <div
      className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
      style={{
        background:
          "linear-gradient(135deg, rgba(99,102,241,0.18) 0%, rgba(99,102,241,0.06) 100%)",
        border: "1px solid rgba(99,102,241,0.3)",
        color: "var(--color-primary)",
      }}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4.5 h-4.5">
        <path d="M12 8V4H8" />
        <rect x="4" y="8" width="16" height="12" rx="2" />
        <path d="M2 14h2M20 14h2M15 13v2M9 13v2" />
      </svg>
    </div>
  );
}
