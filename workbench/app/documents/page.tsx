"use client";

import { useState, useEffect } from "react";
import { uploadDocument, listDocuments, deleteDocument } from "@/lib/api";

export default function DocumentsPage() {
  const [docs, setDocs] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    loadDocs();
  }, []);

  async function loadDocs() {
    try {
      const result = await listDocuments();
      setDocs(result.documents || []);
    } catch {
      setError("Failed to load documents");
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      await uploadDocument(file);
      await loadDocs();
    } catch {
      setError("Upload failed");
    }
    setUploading(false);
  }

  async function handleDelete(docId: string) {
    try {
      await deleteDocument(docId);
      await loadDocs();
    } catch {
      setError("Delete failed");
    }
  }

  return (
    <div>
      <h1>Documents</h1>
      <div className="sovereign-card">
        <h3>Upload Document</h3>
        <input type="file" onChange={handleUpload} disabled={uploading} className="sovereign-input" />
        {uploading && <p>Uploading...</p>}
        {error && <p className="text-red-500">{error}</p>}
      </div>
      <div className="sovereign-card">
        <h3>Document List ({docs.length})</h3>
        {docs.length === 0 ? (
          <p className="text-gray-500">No documents uploaded yet.</p>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="text-left border-b">
                <th className="p-2">Filename</th>
                <th className="p-2">Type</th>
                <th className="p-2">Size</th>
                <th className="p-2">Status</th>
                <th className="p-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((doc) => (
                <tr key={doc.id} className="border-b">
                  <td className="p-2">{doc.original_filename}</td>
                  <td className="p-2">{doc.mime_type}</td>
                  <td className="p-2">{(doc.size_bytes / 1024).toFixed(1)} KB</td>
                  <td className="p-2"><span className="sovereign-badge badge-info">{doc.status}</span></td>
                  <td className="p-2"><button onClick={() => handleDelete(doc.id)} className="text-red-500 hover:underline">Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
