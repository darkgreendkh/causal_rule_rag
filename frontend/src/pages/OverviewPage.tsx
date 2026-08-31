import {
  ArrowRight,
  CheckCircle2,
  FileStack,
  Files,
  MessageCircleQuestion,
  Network,
  Upload,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import type { Page } from '../App'
import { listDocuments, loadGraph } from '../api'
import type { DocumentStatus, DocumentSummary, GraphResponse } from '../types'

const STATUS_LABELS: Record<DocumentStatus, string> = {
  PENDING: '等待处理',
  PARSING: '解析文档',
  EMBEDDING: '生成向量',
  EXTRACTING_GRAPH: '抽取图谱',
  COMPLETED: '已完成',
  FAILED: '处理失败',
}

export default function OverviewPage({ onNavigate }: { onNavigate: (page: Page) => void }) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [graph, setGraph] = useState<GraphResponse>({ nodes: [], edges: [], truncated: false })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    void Promise.all([listDocuments(), loadGraph(null)])
      .then(([documentItems, graphData]) => {
        setDocuments(documentItems)
        setGraph(graphData)
        setError('')
      })
      .catch((requestError: unknown) => {
        setError(requestError instanceof Error ? requestError.message : '概览数据加载失败')
      })
      .finally(() => setLoading(false))
  }, [])

  const completed = documents.filter((document) => document.status === 'COMPLETED').length
  const chunkCount = documents.reduce((total, document) => total + document.total_chunks, 0)

  return (
    <section className="overview-page">
      <div className="page-title">
        <div>
          <p className="section-kicker">RESEARCH WORKSPACE</p>
          <h1>欢迎回来</h1>
          <p>快速管理法规文档、检视知识图谱并开始证据问答。</p>
        </div>
        <button className="primary-button" type="button" onClick={() => onNavigate('documents')}>
          <Upload size={17} />
          上传文档
        </button>
      </div>

      {error && <p className="error-banner">{error}</p>}

      <div className="stat-grid" aria-live="polite">
        <StatCard icon={Files} label="文档总数" value={loading ? '—' : documents.length} />
        <StatCard icon={CheckCircle2} label="已完成文档" value={loading ? '—' : completed} />
        <StatCard icon={FileStack} label="分块总数" value={loading ? '—' : chunkCount} />
        <StatCard
          icon={Network}
          label="可视图谱"
          value={loading ? '—' : `${graph.nodes.length}${graph.truncated ? '+' : ''}`}
          detail={loading ? undefined : `${graph.edges.length} 条关系`}
        />
      </div>

      <div className="overview-grid">
        <div>
          <div className="section-heading">
            <div>
              <p className="section-kicker">QUICK START</p>
              <h2>快速开始</h2>
            </div>
          </div>
          <div className="quick-action-grid">
            <QuickAction
              icon={Files}
              title="文档管理"
              description="上传法规并查看处理进度与原始分块"
              onClick={() => onNavigate('documents')}
            />
            <QuickAction
              icon={Network}
              title="知识图谱"
              description="探索实体、关系及其来源分块"
              onClick={() => onNavigate('graph')}
            />
            <QuickAction
              icon={MessageCircleQuestion}
              title="法规问答"
              description="通过向量或图谱增强检索获取证据回答"
              onClick={() => onNavigate('qa')}
            />
          </div>
        </div>

        <aside className="panel recent-panel">
          <div className="section-heading">
            <div>
              <p className="section-kicker">RECENT DOCUMENTS</p>
              <h2>最近文档</h2>
            </div>
            <button className="text-button" type="button" onClick={() => onNavigate('documents')}>
              查看全部
              <ArrowRight size={15} />
            </button>
          </div>
          {loading ? (
            <p className="muted">正在加载文档…</p>
          ) : documents.length === 0 ? (
            <p className="muted">尚未上传文档。</p>
          ) : (
            <div className="recent-list">
              {documents.slice(0, 4).map((document) => (
                <button type="button" key={document.id} onClick={() => onNavigate('documents')}>
                  <span className="file-icon">{fileExtension(document.filename)}</span>
                  <span>
                    <strong>{document.filename}</strong>
                    <small>{new Date(document.created_at).toLocaleString('zh-CN')}</small>
                  </span>
                  <span className={`status status-${document.status.toLowerCase()}`}>
                    {STATUS_LABELS[document.status]}
                  </span>
                </button>
              ))}
            </div>
          )}
        </aside>
      </div>
    </section>
  )
}

function StatCard({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: LucideIcon
  label: string
  value: string | number
  detail?: string
}) {
  return (
    <article className="panel stat-card">
      <span><Icon size={19} /></span>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
        {detail && <small>{detail}</small>}
      </div>
    </article>
  )
}

function QuickAction({
  icon: Icon,
  title,
  description,
  onClick,
}: {
  icon: LucideIcon
  title: string
  description: string
  onClick: () => void
}) {
  return (
    <button className="panel quick-action" type="button" onClick={onClick}>
      <span><Icon size={23} /></span>
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
      <ArrowRight size={17} />
    </button>
  )
}

function fileExtension(filename: string): string {
  return filename.split('.').pop()?.toUpperCase() ?? 'FILE'
}
