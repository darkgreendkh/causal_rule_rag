import type {
  ChunkView,
  DocumentSummary,
  GraphResponse,
  QAResponse,
  RetrievalMode,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, options)
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(payload?.detail ?? `请求失败（${response.status}）`)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export function listDocuments(): Promise<DocumentSummary[]> {
  return request('/api/documents')
}

export function uploadDocument(file: File): Promise<DocumentSummary> {
  const body = new FormData()
  body.append('file', file)
  return request('/api/documents', { method: 'POST', body })
}

export function listChunks(documentId: string): Promise<ChunkView[]> {
  return request(`/api/documents/${encodeURIComponent(documentId)}/chunks`)
}

export function deleteDocument(documentId: string): Promise<void> {
  return request(`/api/documents/${encodeURIComponent(documentId)}`, { method: 'DELETE' })
}

export function loadGraph(documentId: string | null): Promise<GraphResponse> {
  const query = documentId ? `?document_id=${encodeURIComponent(documentId)}&limit=300` : '?limit=300'
  return request(`/api/graph${query}`)
}

export function askQuestion(question: string, mode: RetrievalMode): Promise<QAResponse> {
  return request('/api/qa', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, mode }),
  })
}
