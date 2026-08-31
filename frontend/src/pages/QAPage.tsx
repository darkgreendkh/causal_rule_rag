import { useState } from 'react'

import { askQuestion } from '../api'
import type { QAResponse, RetrievalMode } from '../types'

export default function QAPage() {
  const [question, setQuestion] = useState('')
  const [mode, setMode] = useState<RetrievalMode>('hybrid')
  const [result, setResult] = useState<QAResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submitQuestion(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalized = question.trim()
    if (!normalized) return
    setLoading(true)
    setError('')
    try {
      setResult(await askQuestion(normalized, mode))
    } catch (requestError) {
      setResult(null)
      setError(requestError instanceof Error ? requestError.message : '问答请求失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="qa-page">
      <div className="panel question-panel">
        <div>
          <p className="section-kicker">EVIDENCE-BASED QA</p>
          <h2>法规问答</h2>
          <p className="muted">每次提问相互独立，回答会同时展示原始 Chunk 与图谱扩展路径。</p>
        </div>

        <div className="mode-switch" aria-label="检索模式">
          <button
            type="button"
            className={mode === 'vector' ? 'active' : ''}
            onClick={() => setMode('vector')}
          >
            <strong>纯向量</strong>
            <span>Top 5 语义分块</span>
          </button>
          <button
            type="button"
            className={mode === 'hybrid' ? 'active' : ''}
            onClick={() => setMode('hybrid')}
          >
            <strong>混合检索</strong>
            <span>向量 + 图谱一跳扩展</span>
          </button>
        </div>

        <form className="question-form" onSubmit={submitQuestion}>
          <textarea
            value={question}
            maxLength={2000}
            placeholder="例如：数据处理者需要履行哪些安全义务？"
            onChange={(event) => setQuestion(event.target.value)}
          />
          <div>
            <span>{question.length} / 2000</span>
            <button className="primary-button" type="submit" disabled={!question.trim() || loading}>
              {loading ? '检索与生成中…' : '提交问题'}
            </button>
          </div>
        </form>
      </div>

      {error && <p className="error-banner">{error}</p>}

      {result ? (
        <div className="answer-layout">
          <article className="panel answer-card">
            <div className="answer-heading">
              <div>
                <p className="section-kicker">ANSWER</p>
                <h2>基于证据的回答</h2>
              </div>
              <span className="mode-pill">
                {result.mode === 'hybrid' ? '混合检索' : '纯向量'}
              </span>
            </div>
            <div className="answer-text">{result.answer}</div>

            {result.graph_paths.length > 0 && (
              <section className="path-section">
                <h3>图谱扩展路径</h3>
                <div className="path-list">
                  {result.graph_paths.map((path, index) => (
                    <div className="path-card" key={`${path.source_chunk_id}-${index}`}>
                      <span>{path.subject}</span>
                      <strong>{path.predicate}</strong>
                      <span>{path.object}</span>
                      <small>{path.source_chunk_id}</small>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </article>

          <aside className="panel evidence-panel">
            <div className="panel-heading">
              <div>
                <p className="section-kicker">SOURCES</p>
                <h2>检索证据</h2>
              </div>
              <span className="count-pill">{result.sources.length}</span>
            </div>
            <div className="evidence-list">
              {result.sources.length === 0 ? (
                <p className="muted">本次没有召回可用证据。</p>
              ) : (
                result.sources.map((source, index) => (
                  <details className="evidence-item" key={source.chunk_id} open={index === 0}>
                    <summary>
                      <span>[S{index + 1}]</span>
                      <div>
                        <strong>{source.filename}</strong>
                        <small>
                          Chunk {source.chunk_index} ·{' '}
                          {source.channel === 'graph' ? '图谱扩展' : '向量召回'}
                          {source.score !== null ? ` · ${source.score.toFixed(3)}` : ''}
                        </small>
                      </div>
                    </summary>
                    <pre>{source.text}</pre>
                  </details>
                ))
              )}
            </div>
          </aside>
        </div>
      ) : (
        <div className="panel qa-empty">
          <span>01</span>
          <p>选择检索模式并输入问题</p>
          <span>02</span>
          <p>系统召回法规原文并扩展图谱关系</p>
          <span>03</span>
          <p>查看带来源标记的回答</p>
        </div>
      )}
    </section>
  )
}
