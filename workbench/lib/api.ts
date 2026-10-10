"use client";

const API_BASE = "/api";

async function fetchJson(url: string, options?: RequestInit): Promise<any> {
  const resp = await fetch(url, options);
  const text = await resp.text();
  if (!resp.ok) {
    throw new Error(`API error ${resp.status}: ${text.substring(0, 200)}`);
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`Invalid JSON response: ${text.substring(0, 200)}`);
  }
}

export async function uploadDocument(file: File): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);
  return fetchJson(`${API_BASE}/documents`, { method: "POST", body: formData });
}

export async function listDocuments(): Promise<any> {
  return fetchJson(`${API_BASE}/documents`);
}

export async function getDocument(docId: string): Promise<any> {
  return fetchJson(`${API_BASE}/documents/${docId}`);
}

export async function deleteDocument(docId: string): Promise<void> {
  await fetch(`${API_BASE}/documents/${docId}`, { method: "DELETE" });
}

export async function search(req: { query: string; top_k?: number; document_id?: string }): Promise<any> {
  return fetchJson(`${API_BASE}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export async function ragQuery(req: { query: string; document_id?: string }): Promise<any> {
  return fetchJson(`${API_BASE}/rag/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export async function agentQuery(req: { query: string; document_id?: string }): Promise<any> {
  return fetchJson(`${API_BASE}/agents/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export async function createDeliverable(req: any): Promise<any> {
  return fetchJson(`${API_BASE}/deliverables`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export async function exportDeliverable(req: any, format: string): Promise<Blob> {
  const resp = await fetch(`${API_BASE}/deliverables/export?format=${format}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!resp.ok) {
    throw new Error(`Export failed: ${resp.status}`);
  }
  return resp.blob();
}

export async function getKBStats(): Promise<any> {
  return fetchJson(`${API_BASE}/kb/stats`);
}

export async function getHealth(): Promise<any> {
  return fetchJson(`${API_BASE}/healthz`);
}
