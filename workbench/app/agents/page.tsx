"use client";

import { useState } from "react";
import { agentQuery } from "@/lib/api";

export default function AgentsPage() {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  async function handleQuery() {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const result = await agentQuery({ query });
      setResponse(result);
    } catch {
      setResponse(null);
    }
    setLoading(false);
  }

  return (
    <div>
      <h1>Agent Orchestration</h1>
      <div className="sovereign-card">
        <p className="text-gray-500 mb-4">
          The supervisor classifies your request and routes to specialized agents (RAG, DocIntel, Vision, Risk, Deliverable).
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g., What are the safety risks for pump P-101?"
            className="sovereign-input"
            onKeyDown={(e) => e.key === "Enter" && handleQuery()}
          />
          <button onClick={handleQuery} disabled={loading} className="sovereign-button">
            {loading ? "Running..." : "Run Agents"}
          </button>
        </div>
      </div>

      {response && (
        <div>
          <div className="sovereign-card">
            <div className="flex justify-between items-center mb-4">
              <h3>Task Type: {response.task_type}</h3>
              <span className={`sovereign-badge ${response.succeeded ? "badge-supported" : "badge-unsupported"}`}>
                {response.succeeded ? "Success" : "Has Errors"}
              </span>
            </div>
            <p className="text-sm text-gray-500">
              Agents executed: {response.steps_completed.join(" → ")}
            </p>
            {response.errors?.length > 0 && (
              <div className="mt-2 text-red-500">
                {response.errors.map((e: string, i: number) => (
                  <p key={i}>{e}</p>
                ))}
              </div>
            )}
          </div>

          {response.rag_response && (
            <div className="sovereign-card">
              <h3>RAG Response</h3>
              <p><strong>Verdict:</strong> {response.rag_response.verdict?.kind}</p>
              {response.rag_response.answer && <p>{response.rag_response.answer}</p>}
            </div>
          )}

          {response.findings?.length > 0 && (
            <div className="sovereign-card">
              <h3>Findings ({response.findings.length})</h3>
              {response.findings.map((f: any, i: number) => (
                <div key={i} className="border-b py-2">
                  <div className="flex justify-between">
                    <span>{f.description}</span>
                    <span className={`sovereign-badge badge-${f.severity.toLowerCase()}`}>
                      {f.severity}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {response.deliverable && (
            <div className="sovereign-card">
              <h3>Deliverable</h3>
              <p><strong>Title:</strong> {response.deliverable.title || response.deliverable.metadata?.title}</p>
              {response.deliverable.sections?.map((s: any, i: number) => (
                <div key={i} className="mt-4">
                  <h4>{s.heading}</h4>
                  {s.content && <p>{s.content}</p>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
