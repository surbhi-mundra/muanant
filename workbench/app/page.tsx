import { getHealth, getKBStats, listDocuments } from "@/lib/api";

export default async function Dashboard() {
  let health: any = null;
  let stats: any = null;
  let docs: any = null;

  try {
    health = await getHealth();
    stats = await getKBStats();
    docs = await listDocuments();
  } catch {
    // API not reachable
  }

  return (
    <div>
      <h1>SOVEREIGN Dashboard</h1>
      <p className="text-gray-500 mb-8">
        On-Premise Agentic AI Workbench for Confidential Industrial Work
      </p>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="sovereign-card">
          <h3>System Status</h3>
          <p className="text-2xl font-bold">
            {health ? health.status : "offline"}
          </p>
          <p className="text-sm text-gray-500">
            Version: {health?.version || "—"}
          </p>
        </div>
        <div className="sovereign-card">
          <h3>Knowledge Base</h3>
          <p className="text-2xl font-bold">
            {stats?.vector_count ?? "—"}
          </p>
          <p className="text-sm text-gray-500">vectors indexed</p>
        </div>
        <div className="sovereign-card">
          <h3>Documents</h3>
          <p className="text-2xl font-bold">
            {docs?.total ?? "—"}
          </p>
          <p className="text-sm text-gray-500">documents uploaded</p>
        </div>
      </div>

      <div className="sovereign-card">
        <h3>Quick Actions</h3>
        <div className="flex gap-4 mt-4">
          <a href="/documents" className="sovereign-button">Upload Document</a>
          <a href="/search" className="sovereign-button">Search KB</a>
          <a href="/rag" className="sovereign-button">Ask Question</a>
          <a href="/agents" className="sovereign-button">Run Agent</a>
        </div>
      </div>
    </div>
  );
}
