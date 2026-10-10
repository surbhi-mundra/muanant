"use client";

import { useState } from "react";
import { createDeliverable, exportDeliverable } from "@/lib/api";

export default function DeliverablesPage() {
  const [query, setQuery] = useState("");
  const [deliverable, setDeliverable] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  async function handleGenerate() {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const result = await createDeliverable({
        deliverable_type: "summary",
        query,
      });
      setDeliverable(result);
    } catch {
      setDeliverable(null);
    }
    setLoading(false);
  }

  async function handleExport(format: string) {
    try {
      const blob = await exportDeliverable({
        deliverable_type: "summary",
        query,
      }, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // export failed
    }
  }

  return (
    <div>
      <h1>Deliverables</h1>
      <div className="sovereign-card">
        <p className="text-gray-500 mb-4">
          Generate structured reports with evidence citations. Export to PDF, DOCX, XLSX, CSV, or JSON.
        </p>
        <div className="flex gap-2 mb-4">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Report topic..."
            className="sovereign-input"
          />
          <button onClick={handleGenerate} disabled={loading} className="sovereign-button">
            {loading ? "Generating..." : "Generate"}
          </button>
        </div>
      </div>

      {deliverable && (
        <div>
          <div className="sovereign-card">
            <h3>{deliverable.title}</h3>
            <p className="text-sm text-gray-500">
              Type: {deliverable.type} | Sections: {deliverable.section_count} |
              Findings: {deliverable.finding_count} | Citations: {deliverable.citation_count}
            </p>
          </div>

          <div className="sovereign-card">
            <h3>Export</h3>
            <div className="flex gap-2 flex-wrap">
              {["pdf", "docx", "xlsx", "csv", "json", "markdown"].map((fmt) => (
                <button key={fmt} onClick={() => handleExport(fmt)} className="sovereign-button">
                  {fmt.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {deliverable.markdown && (
            <div className="sovereign-card">
              <h3>Preview (Markdown)</h3>
              <pre className="whitespace-pre-wrap text-sm">{deliverable.markdown}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
