import {
  Bot,
  Check,
  Database,
  History,
  MessageCircleQuestion,
  Network,
  Pencil,
  Plus,
  Send,
  Trash2,
  User,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { askQuestion } from '../api'
import {
  appendConversationTurn,
  deleteConversation,
  loadConversationStore,
  renameConversation,
  saveConversationStore,
  selectConversation,
  sortConversations,
  startNewConversation as createBlankConversation,
} from '../conversationStore'
import type { ConversationItem } from '../conversationStore'
import { formatSourceChunk } from '../sourceChunks'
import type { ConversationHistoryTurn, RetrievalMode } from '../types'

const MAX_HISTORY_TURNS = 3

export default function QAPage() {
  const messageListRef = useRef<HTMLDivElement>(null)
  const historyMenuRef = useRef<HTMLDivElement>(null)
  const [initialStore] = useState(() => loadConversationStore(
    window.localStorage,
    () => window.crypto.randomUUID(),
  ))
  const migrationPendingRef = useRef(initialStore.migratedLegacy)
  const [question, setQuestion] = useState('')
  const [mode, setMode] = useState<RetrievalMode>('hybrid')
  const [conversationStore, setConversationStore] = useState(initialStore.store)
  const initialConversation = initialStore.store.conversations.find(
    (conversation) => conversation.id === initialStore.store.activeConversationId,
  )
  const [selectedTurnId, setSelectedTurnId] = useState<string | null>(
    initialConversation?.turns[initialConversation.turns.length - 1]?.id ?? null,
  )
  const [pendingQuestion, setPendingQuestion] = useState('')
  const [historyOpen, setHistoryOpen] = useState(false)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renamingTitle, setRenamingTitle] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [storageError, setStorageError] = useState('')

  const activeConversation = useMemo(
    () => conversationStore.conversations.find(
      (conversation) => conversation.id === conversationStore.activeConversationId,
    ) ?? null,
    [conversationStore],
  )
  const turns = useMemo(() => activeConversation?.turns ?? [], [activeConversation])
  const history = useMemo(
    () => sortConversations(conversationStore.conversations),
    [conversationStore.conversations],
  )

  useEffect(() => {
    try {
      saveConversationStore(
        window.localStorage,
        conversationStore,
        migrationPendingRef.current,
      )
      migrationPendingRef.current = false
      setStorageError('')
    } catch {
      setStorageError('浏览器存储空间不足，请删除部分历史对话后重试。')
    }
  }, [conversationStore])

  useEffect(() => {
    if (!historyOpen) return
    function closeHistoryOnOutsideClick(event: PointerEvent) {
      if (!historyMenuRef.current?.contains(event.target as Node)) {
        setHistoryOpen(false)
        setRenamingId(null)
      }
    }
    document.addEventListener('pointerdown', closeHistoryOnOutsideClick)
    return () => document.removeEventListener('pointerdown', closeHistoryOnOutsideClick)
  }, [historyOpen])

  useEffect(() => {
    const messageList = messageListRef.current
    if (messageList) messageList.scrollTop = messageList.scrollHeight
  }, [turns, loading])

  const selectedTurn = useMemo(
    () => turns.find((turn) => turn.id === selectedTurnId) ?? turns[turns.length - 1] ?? null,
    [selectedTurnId, turns],
  )
  const sourceDocuments = selectedTurn?.result.sources.map((source) => ({
    id: source.document_id,
    filename: source.filename,
  })) ?? []

  async function submitQuestion(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalized = question.trim()
    if (!normalized || loading) return
    const history: ConversationHistoryTurn[] = turns.slice(-MAX_HISTORY_TURNS).map((turn) => ({
      question: turn.question,
      answer: turn.result.answer,
    }))
    setPendingQuestion(normalized)
    setQuestion('')
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
      setConversationStore((current) => appendConversationTurn(
        current,
        item,
        window.crypto.randomUUID(),
      ))
      setSelectedTurnId(item.id)
      setPendingQuestion('')
    } catch (requestError) {
      setPendingQuestion('')
      setQuestion((current) => current || normalized)
      setError(requestError instanceof Error ? requestError.message : '问答请求失败')
    } finally {
      setLoading(false)
    }
  }

  function startNewConversation() {
    if (loading) return
    setConversationStore((current) => createBlankConversation(current))
    setSelectedTurnId(null)
    setQuestion('')
    setError('')
    setHistoryOpen(false)
    setRenamingId(null)
  }

  function openConversation(conversationId: string) {
    if (loading) return
    const conversation = conversationStore.conversations.find(
      (item) => item.id === conversationId,
    )
    if (!conversation) return
    setConversationStore((current) => selectConversation(current, conversationId))
    setSelectedTurnId(conversation.turns[conversation.turns.length - 1]?.id ?? null)
    setQuestion('')
    setError('')
    setHistoryOpen(false)
    setRenamingId(null)
  }

  function beginRename(conversationId: string, title: string) {
    if (loading) return
    setRenamingId(conversationId)
    setRenamingTitle(title)
  }

  function finishRename(conversationId: string) {
    setConversationStore((current) => renameConversation(current, conversationId, renamingTitle))
    setRenamingId(null)
  }

  function removeConversation(conversationId: string) {
    if (loading) return
    const deletingActive = conversationStore.activeConversationId === conversationId
    const updated = deleteConversation(conversationStore, conversationId)
    setConversationStore(updated)
    setRenamingId(null)
    if (deletingActive) {
      const next = updated.conversations.find(
        (conversation) => conversation.id === updated.activeConversationId,
      )
      setSelectedTurnId(next?.turns[next.turns.length - 1]?.id ?? null)
      setQuestion('')
      setError('')
    }
  }

  return (
    <section className="qa-page">
      <div className="qa-workspace">
        <div className="panel conversation-panel">
          <div className="conversation-status">
            <span><i /> 法规问答助手</span>
            <small>对话历史保存在本地浏览器</small>
            <div className="conversation-actions">
              <div className="conversation-history-menu" ref={historyMenuRef}>
                <button
                  className="secondary-button"
                  type="button"
                  aria-expanded={historyOpen}
                  onClick={() => setHistoryOpen((open) => !open)}
                  disabled={loading}
                >
                  <History size={17} />
                  历史对话
                </button>
                {historyOpen && (
                  <div className="conversation-history-popover">
                    <div className="conversation-history-heading">
                      <strong>历史对话</strong>
                      <span>{history.length}</span>
                    </div>
                    {history.length === 0 ? (
                      <p className="conversation-history-empty">暂无历史对话</p>
                    ) : (
                      <div className="conversation-history-list">
                        {history.map((conversation) => (
                          <div
                            className={conversation.id === conversationStore.activeConversationId
                              ? 'conversation-history-item active'
                              : 'conversation-history-item'}
                            key={conversation.id}
                          >
                            {renamingId === conversation.id ? (
                              <div className="conversation-rename-form">
                                <input
                                  autoFocus
                                  value={renamingTitle}
                                  aria-label="对话标题"
                                  onChange={(event) => setRenamingTitle(event.target.value)}
                                  onBlur={() => finishRename(conversation.id)}
                                  onKeyDown={(event) => {
                                    if (event.key === 'Enter') event.currentTarget.blur()
                                    if (event.key === 'Escape') setRenamingId(null)
                                  }}
                                />
                                <Check size={15} />
                              </div>
                            ) : (
                              <button
                                className="conversation-history-main"
                                type="button"
                                onClick={() => openConversation(conversation.id)}
                                disabled={loading}
                              >
                                <strong>{conversation.title}</strong>
                                <small>
                                  {formatConversationTime(conversation.updatedAt)}
                                  {' · '}{conversation.turns.length} 轮
                                </small>
                              </button>
                            )}
                            <div className="conversation-history-item-actions">
                              <button
                                type="button"
                                aria-label={`重命名 ${conversation.title}`}
                                title="重命名"
                                onClick={() => beginRename(conversation.id, conversation.title)}
                                disabled={loading}
                              >
                                <Pencil size={14} />
                              </button>
                              <button
                                type="button"
                                aria-label={`删除 ${conversation.title}`}
                                title="删除"
                                onClick={() => removeConversation(conversation.id)}
                                disabled={loading}
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
              <button
                className="secondary-button"
                type="button"
                onClick={startNewConversation}
                disabled={loading}
              >
                <Plus size={17} />
                新对话
              </button>
            </div>
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
                      <span className="answer-text">{turn.result.answer}</span>
                      <small>{turn.result.sources.length} 条证据 · 点击查看详情</small>
                    </button>
                  </div>
                </div>
              ))
            )}

            {pendingQuestion && (
              <div className="conversation-turn">
                <div className="user-message-row">
                  <div className="message-avatar user-avatar"><User size={16} /></div>
                  <div className="user-message">
                    <p>{pendingQuestion}</p>
                  </div>
                </div>
                <div className="assistant-message-row loading-message">
                  <div className="message-avatar bot-avatar"><Bot size={17} /></div>
                  <div><i /><i /><i /><span>正在检索证据并生成回答</span></div>
                </div>
              </div>
            )}
          </div>

          {storageError && <p className="error-banner composer-error">{storageError}</p>}
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
            <h2>本轮证据</h2>
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
                        <small>{formatSourceChunk(path.source_chunk_id, sourceDocuments)}</small>
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

function formatConversationTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}
