"use client";

import { useState } from "react";
import { ragQuery } from "@/lib/api";

export default function RAGPage() {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  async function handleQuery() {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const result = await ragQuery({ query });
      setResponse(result);
    } catch {
      setResponse(null);
    }
    setLoading(false);
  }

  return (
    <div>
      <h1>Ask a Question</h1>
      <div className="sovereign-card">
        <p className="text-gray-500 mb-4">
          Ask a grounded question. The system retrieves evidence, generates an answer, and verifies claims.
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g., What is the maintenance schedule for pump P-101?"
            className="sovereign-input"
            onKeyDown={(e) => e.key === "Enter" && handleQuery()}
          />
          <button onClick={handleQuery} disabled={loading} className="sovereign-button">
            {loading ? "Thinking..." : "Ask"}
          </button>
        </div>
      </div>

      {response && (
        <div>
          <div className="sovereign-card">
            <div className="flex justify-between items-center mb-4">
              <h3>Verdict</h3>
              <span className={`sovereign-badge ${response.verdict === "answered" ? "badge-supported" : "badge-unsupported"}`}>
                {response.verdict}
              </span>
            </div>
            {response.answer && (
              <div>
                <h4>Answer</h4>
                <p>{response.answer}</p>
              </div>
            )}
            {response.verdict_message && response.verdict !== "answered" && (
              <p className="text-orange-500">{response.verdict_message}</p>
            )}
          </div>

          {response.claims?.length > 0 && (
            <div className="sovereign-card">
              <h3>Claims ({response.claims.length})</h3>
              {response.claims.map((c: any, i: number) => (
                <div key={i} className="border-b py-2">
                  <div className="flex justify-between">
                    <span>{c.text}</span>
                    <span className={`sovereign-badge badge-${c.support_status.toLowerCase()}`}>
                      {c.support_status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {response.evidence?.length > 0 && (
            <div className="sovereign-card">
              <h3>Evidence ({response.evidence.length})</h3>
              {response.evidence.map((e: any, i: number) => (
                <div key={i} className="border-b py-2">
                  <p className="text-sm text-gray-500">Doc: {e.document_id.substring(0, 20)}... {e.page ? `p.${e.page}` : ""}</p>
                  <p className="mt-1">{e.text}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
