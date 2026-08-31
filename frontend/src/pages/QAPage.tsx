import {
  Bot,
  Database,
  MessageCircleQuestion,
  Network,
  Plus,
  Send,
  User,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { askQuestion } from '../api'
import type { ConversationHistoryTurn, QAResponse, RetrievalMode } from '../types'

const STORAGE_KEY = 'causal-rule-rag:conversation:v1'
const MAX_STORED_TURNS = 20
const MAX_HISTORY_TURNS = 3

interface ConversationItem {
  id: string
  question: string
  createdAt: string
  result: QAResponse
}

export default function QAPage() {
  const messageListRef = useRef<HTMLDivElement>(null)
  const [question, setQuestion] = useState('')
  const [mode, setMode] = useState<RetrievalMode>('hybrid')
  const [turns, setTurns] = useState<ConversationItem[]>(loadConversation)
  const [selectedTurnId, setSelectedTurnId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!selectedTurnId && turns.length > 0) {
      setSelectedTurnId(turns[turns.length - 1].id)
    }
  }, [selectedTurnId, turns])

  useEffect(() => {
    if (turns.length === 0) {
      window.localStorage.removeItem(STORAGE_KEY)
      return
    }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(turns))
  }, [turns])

  useEffect(() => {
    const messageList = messageListRef.current
    if (messageList) messageList.scrollTop = messageList.scrollHeight
  }, [turns, loading])

  const selectedTurn = useMemo(
    () => turns.find((turn) => turn.id === selectedTurnId) ?? turns[turns.length - 1] ?? null,
    [selectedTurnId, turns],
  )

  async function submitQuestion(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalized = question.trim()
    if (!normalized || loading) return
    const history: ConversationHistoryTurn[] = turns.slice(-MAX_HISTORY_TURNS).map((turn) => ({
      question: turn.question,
      answer: turn.result.answer,
    }))
    setLoading(true)
    setError('')
    try {
      const result = await askQuestion(normalized, mode, history)
      const item: ConversationItem = {
        id: window.crypto.randomUUID(),
        question: normalized,
        createdAt: new Date().toISOString(),
        result,
      }
      setTurns((current) => [...current, item].slice(-MAX_STORED_TURNS))
      setSelectedTurnId(item.id)
      setQuestion('')
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '问答请求失败')
    } finally {
      setLoading(false)
    }
  }

  function startNewConversation() {
    if (turns.length > 0 && !window.confirm('新建对话将清空当前浏览器中的问答记录，是否继续？')) return
    setTurns([])
    setSelectedTurnId(null)
    setQuestion('')
    setError('')
    window.localStorage.removeItem(STORAGE_KEY)
  }

  return (
    <section className="qa-page">
      <div className="page-title qa-page-title">
        <div>
          <p className="section-kicker">CONTEXTUAL LEGAL QA</p>
          <h1>法规问答</h1>
          <p>连续追问法规问题，每轮回答都保留独立证据。</p>
        </div>
        <button className="secondary-button" type="button" onClick={startNewConversation}>
          <Plus size={17} />
          新对话
        </button>
      </div>

      <div className="qa-workspace">
        <div className="panel conversation-panel">
          <div className="conversation-status">
            <span><i /> 法规问答助手</span>
            <small>当前会话保存在本地浏览器</small>
          </div>

          <div className="message-list" ref={messageListRef} aria-live="polite">
            {turns.length === 0 && !loading ? (
              <div className="conversation-empty">
                <span><MessageCircleQuestion size={28} /></span>
                <h2>从一个法规问题开始</h2>
                <p>你可以继续追问“上述义务”“这种情况”等上下文问题。</p>
                <div>
                  <button type="button" onClick={() => setQuestion('数据处理者需要履行哪些安全义务？')}>
                    数据处理者有哪些安全义务？
                  </button>
                  <button type="button" onClick={() => setQuestion('发生数据安全事件后应当如何处理？')}>
                    安全事件应当如何处理？
                  </button>
                </div>
              </div>
            ) : (
              turns.map((turn) => (
                <div className="conversation-turn" key={turn.id}>
                  <div className="user-message-row">
                    <div className="message-avatar user-avatar"><User size={16} /></div>
                    <div className="user-message">
                      <small>你</small>
                      <p>{turn.question}</p>
                    </div>
                  </div>
                  <div className="assistant-message-row">
                    <div className="message-avatar bot-avatar"><Bot size={17} /></div>
                    <button
                      className={turn.id === selectedTurn?.id ? 'assistant-message selected' : 'assistant-message'}
                      type="button"
                      onClick={() => setSelectedTurnId(turn.id)}
                    >
                      <span className="assistant-message-heading">
                        <strong>法规问答助手</strong>
                        <span className="mode-pill">
                          {turn.result.mode === 'hybrid' ? '混合检索' : '纯向量'}
                        </span>
                      </span>
                      <span className="answer-text">{turn.result.answer}</span>
                      <small>{turn.result.sources.length} 条证据 · 点击查看详情</small>
                    </button>
                  </div>
                </div>
              ))
            )}

            {loading && (
              <div className="assistant-message-row loading-message">
                <div className="message-avatar bot-avatar"><Bot size={17} /></div>
                <div><i /><i /><i /><span>正在检索证据并生成回答</span></div>
              </div>
            )}
          </div>

          {error && <p className="error-banner composer-error">{error}</p>}

          <form className="question-composer" onSubmit={submitQuestion}>
            <div className="compact-mode-switch" aria-label="检索模式">
              <button
                type="button"
                className={mode === 'vector' ? 'active' : ''}
                onClick={() => setMode('vector')}
              >
                <Database size={14} />
                纯向量
              </button>
              <button
                type="button"
                className={mode === 'hybrid' ? 'active' : ''}
                onClick={() => setMode('hybrid')}
              >
                <Network size={14} />
                混合检索
              </button>
            </div>
            <div className="composer-input">
              <textarea
                value={question}
                maxLength={2000}
                rows={2}
                placeholder="输入法规问题，Enter 发送，Shift + Enter 换行"
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                    event.preventDefault()
                    event.currentTarget.form?.requestSubmit()
                  }
                }}
              />
              <span>{question.length} / 2000</span>
              <button type="submit" aria-label="发送问题" disabled={!question.trim() || loading}>
                <Send size={18} />
              </button>
            </div>
          </form>
        </div>

        <aside className="panel conversation-evidence">
          <div className="section-heading">
            <div>
              <p className="section-kicker">CURRENT EVIDENCE</p>
              <h2>本轮证据</h2>
            </div>
            {selectedTurn && <span className="count-pill">{selectedTurn.result.sources.length}</span>}
          </div>
          {!selectedTurn ? (
            <div className="detail-empty compact">
              <Database size={28} />
              <p>完成一次提问后，可在这里核对原文和图谱路径。</p>
            </div>
          ) : (
            <>
              <p className="selected-question">{selectedTurn.question}</p>
              <div className="evidence-list">
                {selectedTurn.result.sources.length === 0 ? (
                  <p className="muted">本轮没有召回可用证据。</p>
                ) : (
                  selectedTurn.result.sources.map((source, index) => (
                    <details className="evidence-item" key={source.chunk_id} open={index === 0}>
                      <summary>
                        <span>[S{index + 1}]</span>
                        <div>
                          <strong>{source.filename}</strong>
                          <small>
                            Chunk {source.chunk_index} · {source.channel === 'graph' ? '图谱扩展' : '向量召回'}
                            {source.score !== null ? ` · ${source.score.toFixed(3)}` : ''}
                          </small>
                        </div>
                      </summary>
                      <pre>{source.text}</pre>
                    </details>
                  ))
                )}
              </div>

              {selectedTurn.result.graph_paths.length > 0 && (
                <section className="path-section">
                  <h3>图谱扩展路径</h3>
                  <div className="path-list">
                    {selectedTurn.result.graph_paths.map((path, index) => (
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
            </>
          )}
        </aside>
      </div>
    </section>
  )
}

function loadConversation(): ConversationItem[] {
  const stored = window.localStorage.getItem(STORAGE_KEY)
  if (!stored) return []
  try {
    const parsed: unknown = JSON.parse(stored)
    if (!Array.isArray(parsed) || !parsed.every(isConversationItem)) throw new Error('invalid')
    return parsed.slice(-MAX_STORED_TURNS)
  } catch {
    window.localStorage.removeItem(STORAGE_KEY)
    return []
  }
}

function isConversationItem(value: unknown): value is ConversationItem {
  if (!value || typeof value !== 'object') return false
  const item = value as Partial<ConversationItem>
  return (
    typeof item.id === 'string' &&
    typeof item.question === 'string' &&
    typeof item.createdAt === 'string' &&
    !!item.result &&
    typeof item.result.answer === 'string' &&
    (item.result.mode === 'vector' || item.result.mode === 'hybrid') &&
    Array.isArray(item.result.sources) &&
    Array.isArray(item.result.graph_paths)
  )
}
