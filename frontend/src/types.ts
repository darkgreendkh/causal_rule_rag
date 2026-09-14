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
  layer?: string
  community_id?: string
  evidence?: Evidence[]
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  predicate: string
  source_chunk_id: string
  type?: string
  layer?: string
  rpc?: number
  scs?: number
  evidence?: Evidence[]
  rule_ids?: string[]
}

export interface GraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
  truncated: boolean
  communities?: Community[]
  build_id?: string
}

export type RetrievalMode = 'vector' | 'hybrid' | 'causal'

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
  causal_paths?: CausalPath[]
  rule_checks?: RuleCheck[]
  communities?: Community[]
  knowledge_gaps?: string[]
  run_id?: string
}

export interface Evidence {
  unit_id: string
  source_path: string
  title: string
  article: string
  quote: string
}

export interface MatterField {
  id: string
  label: string
  type: 'boolean' | 'number' | 'date' | 'enum' | 'text' | 'set'
  role: 'applicant' | 'policy' | 'external'
  unit?: string
  options?: string[]
  mutable?: boolean
}

export type Facts = Record<string, unknown>

export interface Matter {
  id: string
  name: string
  category: string
  description: string
  fields: MatterField[]
  policy_parameters: Facts
  rule_ids: string[]
  action_ids: string[]
  goals: { id: string; label: string; condition: Facts }[]
  capabilities: { retrievable: boolean; checkable: boolean; simulatable: boolean; repairable: boolean }
  gaps: string[]
  source_unit_ids: string[]
}

export type RuleStatus = 'candidate' | 'active' | 'rejected' | 'disabled'
export interface ResearchRule {
  id: string
  matter_id: string
  label: string
  condition: Facts
  action_id: string | null
  scope: { region: string; valid_from: string | null; valid_to: string | null; validity_known: boolean }
  evidence: Evidence[]
  status: RuleStatus
  review_source: string
  validation_errors: string[]
}

export interface ResearchAction {
  id: string
  matter_id: string
  label: string
  preconditions: Facts
  effects: Facts
  kind: 'user' | 'external'
  evidence: Evidence[]
}

export interface ResearchProfile { id: string; label: string; description: string }
export interface ResearchStatus {
  status: string
  stage: string
  error: string | null
  build_id: string | null
  profile: string
  counts: Record<string, number>
}
export interface ResearchSummary {
  counts: Record<string, number>
  matters: Matter[]
  documents: { id: string; filename: string; source_path: string; source_url?: string; category: string; region: string; unit_count: number }[]
  profiles: ResearchProfile[]
  build_id: string | null
  gaps: string[]
}
export interface ResearchUnit {
  id: string
  document_id: string
  source_path: string
  title: string
  article: string
  text: string
  category: string
  region: string
  valid_from: string | null
  valid_to: string | null
  validity_known: boolean
}
export interface Coverage {
  unit_id: string
  matter_ids: string[]
  disposition: 'mapped' | 'excluded'
  reason: string
}
export interface Community {
  id: string
  label?: string
  level?: number
  node_count?: number
  parent_id?: string
  unsplittable?: boolean
}
export interface CausalPath {
  id: string
  node_ids: string[]
  edge_ids: string[]
  labels: string[]
  score: number
  semantic_score: number
  rpc: number
  entropy: number
  evidence: Evidence[]
  rule_ids: string[]
}
export interface RuleCheck { rule_id: string | null; label: string; status: string; evidence: Evidence[]; used_for_answer?: boolean }
export interface ResearchContext { dataset?: 'uploaded' | 'research'; matter_id?: string; region: string; as_of: string; facts?: Facts; completed_steps?: string[]; profile?: string }
export interface WorkflowRequest extends ResearchContext {
  matter_id: string
  facts: Facts
  steps: string[]
  completed_steps: string[]
  goal: string
}
export interface WorkflowCheck {
  status: string
  checks: RuleCheck[]
  first_error: { index: number; action_id: string | null; kind: string; message: string } | null
  missing_fields: string[]
  knowledge_gaps: string[]
  state: Facts
  completed_steps: string[]
  goal_satisfied: boolean | string | null
}
export interface WorkflowRepair {
  status: 'repaired' | 'already_valid' | 'unknown' | 'unreachable' | 'truncated'
  edits: unknown[]
  steps: string[]
  cost: number | null
  checked: WorkflowCheck | null
  explored_states: number
  truncated: boolean
}
export interface NextCandidate {
  action_id: string
  label: string
  status: string
  missing_fields: string[]
  evidence: Evidence[]
  preview_state: Facts | null
}
export interface WorkflowNext { status: string; candidates: NextCandidate[]; state: Facts }
