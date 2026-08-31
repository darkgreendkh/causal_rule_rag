import { useCallback, useEffect, useState } from 'react'

import { deleteDocument, listChunks, listDocuments, uploadDocument } from '../api'
import type { ChunkView, DocumentStatus, DocumentSummary } from '../types'

const STATUS_LABELS: Record<DocumentStatus, string> = {
  PENDING: '等待处理',
  PARSING: '解析文档',
  EMBEDDING: '生成向量',
  EXTRACTING_GRAPH: '抽取图谱',
  COMPLETED: '已完成',
  FAILED: '处理失败',
}

const ACTIVE_STATUSES = new Set<DocumentStatus>([
  'PENDING',
  'PARSING',
  'EMBEDDING',
  'EXTRACTING_GRAPH',
])

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [selectedDocument, setSelectedDocument] = useState<DocumentSummary | null>(null)
  const [chunks, setChunks] = useState<ChunkView[]>([])
  const [uploading, setUploading] = useState(false)
  const [loadingChunks, setLoadingChunks] = useState(false)
  const [error, setError] = useState('')

  const refreshDocuments = useCallback(async () => {
    try {
      setDocuments(await listDocuments())
      setError('')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '文档列表加载失败')
    }
  }, [])

  useEffect(() => {
    void refreshDocuments()
    const timer = window.setInterval(() => void refreshDocuments(), 3000)
    return () => window.clearInterval(timer)
  }, [refreshDocuments])

  async function handleUpload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedFile) return
    setUploading(true)
    setError('')
    try {
      await uploadDocument(selectedFile)
      setSelectedFile(null)
      event.currentTarget.reset()
      await refreshDocuments()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '上传失败')
    } finally {
      setUploading(false)
    }
  }

  async function showChunks(document: DocumentSummary) {
    setSelectedDocument(document)
    setLoadingChunks(true)
    setError('')
    try {
      setChunks(await listChunks(document.id))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '分块加载失败')
      setChunks([])
    } finally {
      setLoadingChunks(false)
    }
  }

  async function removeDocument(document: DocumentSummary) {
    if (!window.confirm(`确认删除“${document.filename}”及其全部图谱数据吗？`)) return
    try {
      await deleteDocument(document.id)
      if (selectedDocument?.id === document.id) {
        setSelectedDocument(null)
        setChunks([])
      }
      await refreshDocuments()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '删除失败')
    }
  }

  return (
    <section className="page-grid documents-page">
      <div className="main-column">
        <div className="panel upload-panel">
          <div>
            <p className="section-kicker">DOCUMENT INGESTION</p>
            <h2>上传法规文档</h2>
            <p className="muted">支持 UTF-8 编码的 TXT 与 Markdown，系统会自动分块并构建图谱。</p>
          </div>
          <form className="upload-form" onSubmit={handleUpload}>
            <label className="file-picker">
              <input
                type="file"
                accept=".txt,.md,text/plain,text/markdown"
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              />
              <span>{selectedFile?.name ?? '选择 TXT / MD 文件'}</span>
            </label>
            <button className="primary-button" type="submit" disabled={!selectedFile || uploading}>
              {uploading ? '上传中…' : '上传并处理'}
            </button>
          </form>
        </div>

        {error && <p className="error-banner">{error}</p>}

        <div className="document-list" aria-live="polite">
          {documents.length === 0 ? (
            <div className="panel empty-card">
              <p>尚未上传文档</p>
              <span>上传第一份法规后，处理状态会显示在这里。</span>
            </div>
          ) : (
            documents.map((document) => (
              <article className="panel document-card" key={document.id}>
                <div className="document-meta">
                  <span className={`status status-${document.status.toLowerCase()}`}>
                    {STATUS_LABELS[document.status]}
                  </span>
                  <time>{new Date(document.created_at).toLocaleString('zh-CN')}</time>
                </div>
                <h3>{document.filename}</h3>
                <p className="hash">SHA-256 · {document.sha256.slice(0, 16)}…</p>
                {ACTIVE_STATUSES.has(document.status) && (
                  <div className="progress-block">
                    <div className="progress-track">
                      <span
                        style={{
                          width: `${progressPercent(document)}%`,
                        }}
                      />
                    </div>
                    <small>
                      {document.processed_chunks} / {document.total_chunks || '待解析'} 个分块
                    </small>
                  </div>
                )}
                {document.error && <p className="document-error">{document.error}</p>}
                <div className="card-actions">
                  <button
                    type="button"
                    onClick={() => void showChunks(document)}
                    disabled={document.status !== 'COMPLETED'}
                  >
                    查看分块
                  </button>
                  <button className="danger-button" type="button" onClick={() => void removeDocument(document)}>
                    删除
                  </button>
                </div>
              </article>
            ))
          )}
        </div>
      </div>

      <aside className="panel chunk-panel">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">CHUNKS</p>
            <h2>{selectedDocument?.filename ?? '文档分块'}</h2>
          </div>
          {selectedDocument && <span className="count-pill">{chunks.length}</span>}
        </div>
        {loadingChunks ? (
          <p className="muted">正在加载分块…</p>
        ) : chunks.length ? (
          <div className="chunk-list">
            {chunks.map((chunk) => (
              <article className="chunk-card" key={chunk.id}>
                <div>
                  <span>Chunk {chunk.index}</span>
                  <strong>{chunk.article_no ?? chunk.heading ?? '正文'}</strong>
                </div>
                <pre>{chunk.text}</pre>
              </article>
            ))}
          </div>
        ) : (
          <p className="muted">选择一份已完成的文档查看原始分块。</p>
        )}
      </aside>
    </section>
  )
}

function progressPercent(document: DocumentSummary): number {
  if (document.status === 'PENDING') return 8
  if (document.status === 'PARSING') return 20
  if (document.status === 'EMBEDDING') return 45
  if (!document.total_chunks) return 65
  return 65 + Math.round((document.processed_chunks / document.total_chunks) * 30)
}
