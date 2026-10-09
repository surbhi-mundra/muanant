export default function AuditPage() {
  return (
    <div>
      <h1>Audit Log</h1>
      <div className="sovereign-card">
        <p className="text-gray-500">
          The audit log is a hash-chained, append-only record of all system actions.
          Each entry links to the previous one via SHA-256, making tampering detectable.
        </p>
      </div>
      <div className="sovereign-card">
        <h3>Audit Chain Verification</h3>
        <p className="text-sm text-gray-500 mb-4">
          Run the verification script to check chain integrity:
        </p>
        <pre className="bg-gray-900 text-green-400 p-4 rounded text-sm">
          python scripts/verify_audit_chain.py
        </pre>
      </div>
      <div className="sovereign-card">
        <h3>Audit Event Categories</h3>
        <ul className="list-disc list-inside text-gray-500">
          <li><strong>ingestion</strong> — document upload, parse, delete</li>
          <li><strong>rag</strong> — queries, evidence retrieval</li>
          <li><strong>agents</strong> — agent execution, task routing</li>
          <li><strong>security</strong> — auth, egress attempts, injection detection</li>
          <li><strong>approvals</strong> — HITL approval decisions</li>
        </ul>
      </div>
    </div>
  );
}
