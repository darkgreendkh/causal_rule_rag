import {
  FileText,
  Search,
  Trash2,
  UploadCloud,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

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
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null)
  const [chunks, setChunks] = useState<ChunkView[]>([])
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<DocumentStatus | 'ALL'>('ALL')
  const [uploading, setUploading] = useState(false)
  const [loadingChunks, setLoadingChunks] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')

  const refreshDocuments = useCallback(async () => {
    try {
      const items = await listDocuments()
      setDocuments(items)
      setSelectedDocumentId((current) => {
        if (current && items.some((item) => item.id === current)) return current
        return items[0]?.id ?? null
      })
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

  const selectedDocument = documents.find((item) => item.id === selectedDocumentId) ?? null

  useEffect(() => {
    if (!selectedDocumentId || selectedDocument?.status !== 'COMPLETED') {
      setChunks([])
      return
    }
    let active = true
    setLoadingChunks(true)
    void listChunks(selectedDocumentId)
      .then((items) => {
        if (active) setChunks(items)
      })
      .catch((requestError: unknown) => {
        if (!active) return
        setChunks([])
        setError(requestError instanceof Error ? requestError.message : '分块加载失败')
      })
      .finally(() => {
        if (active) setLoadingChunks(false)
      })
    return () => {
      active = false
    }
  }, [selectedDocumentId, selectedDocument?.status])

  const filteredDocuments = useMemo(() => {
    const keyword = search.trim().toLocaleLowerCase()
    return documents.filter((document) => {
      const matchesSearch = !keyword || document.filename.toLocaleLowerCase().includes(keyword)
      const matchesStatus = statusFilter === 'ALL' || document.status === statusFilter
      return matchesSearch && matchesStatus
    })
  }, [documents, search, statusFilter])

  async function handleUpload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedFile) return
    setUploading(true)
    setError('')
    try {
      const created = await uploadDocument(selectedFile)
      setSelectedDocumentId(created.id)
      setSelectedFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      await refreshDocuments()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '上传失败')
    } finally {
      setUploading(false)
    }
  }

  async function removeDocument(document: DocumentSummary) {
    if (!window.confirm(`确认删除“${document.filename}”及其全部图谱数据吗？`)) return
    try {
      await deleteDocument(document.id)
      await refreshDocuments()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '删除失败')
    }
  }

  function chooseDroppedFile(event: React.DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setDragging(false)
    const file = event.dataTransfer.files[0]
    if (file) setSelectedFile(file)
  }

  return (
    <section className="documents-page">
      <div className="page-title">
        <div>
          <p className="section-kicker">DOCUMENT WORKSPACE</p>
          <h1>文档管理</h1>
          <p>上传法规文档，并检查处理状态和原始分块。</p>
        </div>
      </div>

      <form className="panel compact-upload" onSubmit={handleUpload}>
        <label
          className={dragging ? 'drop-zone dragging' : 'drop-zone'}
          onDragEnter={() => setDragging(true)}
          onDragLeave={() => setDragging(false)}
          onDragOver={(event) => event.preventDefault()}
          onDrop={chooseDroppedFile}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.md,text/plain,text/markdown"
            onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
          />
          <UploadCloud size={24} />
          <span>
            <strong>{selectedFile?.name ?? '点击选择或拖入法规文档'}</strong>
            <small>支持 UTF-8 编码的 TXT、Markdown</small>
          </span>
        </label>
        <button className="primary-button" type="submit" disabled={!selectedFile || uploading}>
          {uploading ? '上传中…' : '上传并处理'}
        </button>
      </form>

      {error && <p className="error-banner">{error}</p>}

      <div className="document-workspace">
        <div className="panel document-browser">
          <div className="document-toolbar">
            <label className="search-field">
              <Search size={16} />
              <input
                type="search"
                value={search}
                placeholder="搜索文档名称"
                aria-label="搜索文档名称"
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
            <select
              value={statusFilter}
              aria-label="筛选文档状态"
              onChange={(event) => setStatusFilter(event.target.value as DocumentStatus | 'ALL')}
            >
              <option value="ALL">全部状态</option>
              {Object.entries(STATUS_LABELS).map(([status, label]) => (
                <option value={status} key={status}>{label}</option>
              ))}
            </select>
          </div>

          <div className="document-table-head" aria-hidden="true">
            <span>文档名称</span>
            <span>分块</span>
            <span>上传时间</span>
            <span>状态</span>
            <span />
          </div>
          <div className="document-table" aria-live="polite">
            {filteredDocuments.length === 0 ? (
              <div className="table-empty">
                <FileText size={26} />
                <span>{documents.length ? '没有符合条件的文档' : '尚未上传文档'}</span>
              </div>
            ) : (
              filteredDocuments.map((document) => (
                <article
                  className={document.id === selectedDocumentId ? 'document-row active' : 'document-row'}
                  key={document.id}
                >
                  <button
                    className="document-select"
                    type="button"
                    onClick={() => setSelectedDocumentId(document.id)}
                  >
                    <span className="document-name-cell">
                      <span className="file-icon">{fileExtension(document.filename)}</span>
                      <strong>{document.filename}</strong>
                    </span>
                    <span>{document.total_chunks || '—'}</span>
                    <time>{new Date(document.created_at).toLocaleDateString('zh-CN')}</time>
                    <span className={`status status-${document.status.toLowerCase()}`}>
                      {STATUS_LABELS[document.status]}
                    </span>
                  </button>
                  <button
                    className="icon-button danger-button"
                    type="button"
                    aria-label={`删除 ${document.filename}`}
                    onClick={(event) => {
                      event.stopPropagation()
                      void removeDocument(document)
                    }}
                  >
                    <Trash2 size={15} />
                  </button>
                </article>
              ))
            )}
          </div>
        </div>

        <aside className="panel document-detail">
          {!selectedDocument ? (
            <div className="detail-empty">
              <FileText size={30} />
              <p>选择一份文档查看信息与分块。</p>
            </div>
          ) : (
            <>
              <div className="document-detail-heading">
                <div>
                  <p className="section-kicker">DOCUMENT DETAIL</p>
                  <h2>{selectedDocument.filename}</h2>
                </div>
                <span className={`status status-${selectedDocument.status.toLowerCase()}`}>
                  {STATUS_LABELS[selectedDocument.status]}
                </span>
              </div>

              <dl className="document-summary">
                <div><dt>文档类型</dt><dd>{fileExtension(selectedDocument.filename)}</dd></div>
                <div><dt>分块数量</dt><dd>{selectedDocument.total_chunks || '—'}</dd></div>
                <div><dt>上传时间</dt><dd>{new Date(selectedDocument.created_at).toLocaleString('zh-CN')}</dd></div>
                <div><dt>文件指纹</dt><dd>{selectedDocument.sha256.slice(0, 16)}…</dd></div>
              </dl>

              {ACTIVE_STATUSES.has(selectedDocument.status) && (
                <div className="progress-block">
                  <div className="progress-label">
                    <span>{STATUS_LABELS[selectedDocument.status]}</span>
                    <small>{selectedDocument.processed_chunks} / {selectedDocument.total_chunks || '待解析'}</small>
                  </div>
                  <div className="progress-track">
                    <span style={{ width: `${progressPercent(selectedDocument)}%` }} />
                  </div>
                </div>
              )}
              {selectedDocument.error && <p className="document-error">{selectedDocument.error}</p>}

              <div className="chunk-heading">
                <div>
                  <h3>分块预览</h3>
                  <p>按法规原文顺序展示</p>
                </div>
                {selectedDocument.status === 'COMPLETED' && <span className="count-pill">{chunks.length}</span>}
              </div>
              {loadingChunks ? (
                <p className="muted">正在加载分块…</p>
              ) : chunks.length > 0 ? (
                <div className="chunk-list">
                  {chunks.map((chunk) => (
                    <article className="chunk-card" key={chunk.id}>
                      <div>
                        <span>Chunk {String(chunk.index).padStart(3, '0')}</span>
                        <strong>{chunk.article_no ?? chunk.heading ?? '正文'}</strong>
                      </div>
                      <pre>{chunk.text}</pre>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="muted">
                  {selectedDocument.status === 'COMPLETED'
                    ? '该文档没有可展示的分块。'
                    : '文档处理完成后将在这里展示分块。'}
                </p>
              )}
            </>
          )}
        </aside>
      </div>
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

function fileExtension(filename: string): string {
  return filename.split('.').pop()?.toUpperCase() ?? 'FILE'
}
