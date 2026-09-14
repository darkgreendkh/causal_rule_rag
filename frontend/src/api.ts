import type {
  ChunkView,
  ConversationHistoryTurn,
  DocumentSummary,
  GraphResponse,
  QAResponse,
  RetrievalMode,
  Coverage,
  Matter,
  ResearchAction,
  ResearchContext,
  ResearchRule,
  ResearchStatus,
  ResearchSummary,
  ResearchUnit,
  RuleStatus,
  WorkflowCheck,
  WorkflowNext,
  WorkflowRepair,
  WorkflowRequest,
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

export function askQuestion(
  question: string,
  mode: RetrievalMode,
  history: ConversationHistoryTurn[] = [],
  context?: ResearchContext,
): Promise<QAResponse> {
  return request('/api/qa', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, mode, history, ...context }),
  })
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}

export const loadResearchSummary = () => request<ResearchSummary>('/api/research/summary')
export const loadResearchStatus = () => request<ResearchStatus>('/api/research/status')
export const buildResearch = (profile: string) => post<ResearchStatus>('/api/research/build', { profile })
export const listMatters = () => request<Matter[]>('/api/research/matters')
export const loadCoverage = () => request<Coverage[]>('/api/research/coverage')
export const listResearchUnits = (documentId: string) => request<ResearchUnit[]>(`/api/research/units?document_id=${encodeURIComponent(documentId)}`)
export const loadResearchUnit = (unitId: string) => request<ResearchUnit>(`/api/research/source/${encodeURIComponent(unitId)}`)
export const removeResearchDocument = (documentId: string) => request<void>(`/api/research/documents/${encodeURIComponent(documentId)}`, { method: 'DELETE' })
export const extractCandidateRules = (matterId: string, unitId: string) =>
  post<{ rules: ResearchRule[]; build_id: string }>('/api/research/rules/extract', { matter_id: matterId, unit_ids: [unitId] })
export const listActions = (matterId: string) => request<ResearchAction[]>(`/api/research/actions?matter_id=${encodeURIComponent(matterId)}`)
export function listRules(matterId = '', status: RuleStatus | '' = '') {
  const params = new URLSearchParams()
  if (matterId) params.set('matter_id', matterId)
  if (status) params.set('status', status)
  return request<ResearchRule[]>(`/api/research/rules?${params}`)
}
export const reviewRules = (ruleIds: string[], action: 'activate' | 'reject' | 'disable') =>
  post<{ results: { id: string; status: string; error?: string }[]; build_id: string }>(
    '/api/research/rules/review', { rule_ids: ruleIds, action },
  )
export function loadResearchGraph(layer: string, matterId: string, communityId: string) {
  const params = new URLSearchParams({ layer, limit: '300' })
  if (matterId) params.set('matter_id', matterId)
  if (communityId) params.set('community_id', communityId)
  return request<GraphResponse>(`/api/research/graph?${params}`)
}
export const checkWorkflow = (body: WorkflowRequest) => post<WorkflowCheck>('/api/research/workflow/check', body)
export const repairWorkflow = (body: WorkflowRequest) => post<WorkflowRepair>('/api/research/workflow/repair', body)
export const nextWorkflow = (body: WorkflowRequest) => post<WorkflowNext>('/api/research/workflow/next', body)
