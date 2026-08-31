export type DocumentStatus =
  | 'PENDING'
  | 'PARSING'
  | 'EMBEDDING'
  | 'EXTRACTING_GRAPH'
  | 'COMPLETED'
  | 'FAILED'

export interface DocumentSummary {
  id: string
  filename: string
  sha256: string
  status: DocumentStatus
  total_chunks: number
  processed_chunks: number
  error: string | null
  created_at: string
}

export interface ChunkView {
  id: string
  document_id: string
  index: number
  text: string
  heading: string | null
  article_no: string | null
}

export interface GraphNode {
  id: string
  label: string
  type: string
  source_chunk_ids: string[]
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  predicate: string
  source_chunk_id: string
}

export interface GraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
  truncated: boolean
}

export type RetrievalMode = 'vector' | 'hybrid'

export interface ConversationHistoryTurn {
  question: string
  answer: string
}

export interface Source {
  chunk_id: string
  document_id: string
  filename: string
  chunk_index: number
  text: string
  heading: string | null
  article_no: string | null
  score: number | null
  channel: 'vector' | 'graph'
}

export interface GraphPath {
  subject: string
  predicate: string
  object: string
  source_chunk_id: string
}

export interface QAResponse {
  answer: string
  mode: RetrievalMode
  sources: Source[]
  graph_paths: GraphPath[]
}
