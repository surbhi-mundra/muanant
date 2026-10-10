"use client";

import { useState } from "react";
import { search } from "@/lib/api";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleSearch() {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const result = await search({ query, top_k: 10 });
      setResults(result.results || []);
    } catch {
      setResults([]);
    }
    setLoading(false);
  }

  return (
    <div>
      <h1>Search Knowledge Base</h1>
      <div className="sovereign-card">
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search for equipment, procedures, findings..."
            className="sovereign-input"
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <button onClick={handleSearch} disabled={loading} className="sovereign-button">
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
      </div>
      <div>
        {results.length > 0 && (
          <div className="sovereign-card">
            <h3>Results ({results.length})</h3>
            {results.map((r, i) => (
              <div key={i} className="border-b py-3">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-mono text-sm text-gray-500">Doc: {r.document_id.substring(0, 20)}...</p>
                    {r.page && <p className="text-sm text-gray-500">Page {r.page}</p>}
                  </div>
                  <span className="sovereign-badge badge-info">Score: {r.score.toFixed(4)}</span>
                </div>
                <p className="mt-2">{r.text}</p>
                {r.section_path?.length > 0 && (
                  <p className="text-sm text-gray-500 mt-1">§ {r.section_path.join(" > ")}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
