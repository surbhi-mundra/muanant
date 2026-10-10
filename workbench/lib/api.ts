"use client";

const API_BASE = "/api";

export async function uploadDocument(file: File): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);
  const resp = await fetch(`${API_BASE}/documents`, {
    method: "POST",
    body: formData,
  });
  return resp.json();
}

export async function listDocuments(): Promise<any> {
  const resp = await fetch(`${API_BASE}/documents`);
  return resp.json();
}

export async function getDocument(docId: string): Promise<any> {
  const resp = await fetch(`${API_BASE}/documents/${docId}`);
  return resp.json();
}

export async function deleteDocument(docId: string): Promise<void> {
  await fetch(`${API_BASE}/documents/${docId}`, { method: "DELETE" });
}

export async function search(req: { query: string; top_k?: number; document_id?: string }): Promise<any> {
  const resp = await fetch(`${API_BASE}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return resp.json();
}

export async function ragQuery(req: { query: string; document_id?: string }): Promise<any> {
  const resp = await fetch(`${API_BASE}/rag/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return resp.json();
}

export async function agentQuery(req: { query: string; document_id?: string }): Promise<any> {
  const resp = await fetch(`${API_BASE}/agents/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return resp.json();
}

export async function createDeliverable(req: any): Promise<any> {
  const resp = await fetch(`${API_BASE}/deliverables`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return resp.json();
}

export async function exportDeliverable(req: any, format: string): Promise<Blob> {
  const resp = await fetch(`${API_BASE}/deliverables/export?format=${format}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return resp.blob();
}

export async function getKBStats(): Promise<any> {
  const resp = await fetch(`${API_BASE}/kb/stats`);
  return resp.json();
}

export async function getHealth(): Promise<any> {
  const resp = await fetch(`${API_BASE}/healthz`);
  return resp.json();
}
