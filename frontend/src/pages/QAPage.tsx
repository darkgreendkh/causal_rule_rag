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
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { askQuestion, loadResearchSummary } from '../api'
import WorkflowPanel from '../components/WorkflowPanel'
import { CausalPaths, GapList, RuleChecks } from '../components/ResearchEvidence'
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
import type { ConversationHistoryTurn, Facts, ResearchContext, ResearchSummary, RetrievalMode } from '../types'

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
  const [research, setResearch] = useState<ResearchSummary | null>(null)
  const [researchError, setResearchError] = useState('')
  const [matterId, setMatterId] = useState('')
  const [region, setRegion] = useState('武汉')
  const [asOf, setAsOf] = useState(() => new Date().toLocaleDateString('en-CA'))
  const [profile, setProfile] = useState('full')
  const [dataset, setDataset] = useState<'uploaded' | 'research'>('uploaded')
  const [facts, setFacts] = useState<Facts>({})
  const [completedSteps, setCompletedSteps] = useState<string[]>([])
  const matter = research?.matters.find((item) => item.id === matterId)
  const context: ResearchContext = { dataset, matter_id: dataset === 'research' ? matterId || undefined : undefined, region, as_of: asOf, profile, facts: dataset === 'research' ? facts : {}, completed_steps: dataset === 'research' ? completedSteps : [] }

  useEffect(() => {
    void loadResearchSummary().then((data) => { setResearch(data); if (data.build_id) setDataset('research') }).catch((err: unknown) => setResearchError(err instanceof Error ? err.message : '研究事项加载失败'))
  }, [])

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
      const result = await askQuestion(normalized, mode, history, context)
      const item: ConversationItem = {
        id: window.crypto.randomUUID(),
        question: normalized,
        createdAt: new Date().toISOString(),
        result,
        context,
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
      <div className="panel research-context">
        <div className="research-toolbar">
          <label>问答资料库<select aria-label="问答资料库" value={dataset} disabled={loading} onChange={(event) => { setDataset(event.target.value as 'uploaded' | 'research'); if (event.target.value === 'uploaded' && mode === 'causal') setMode('hybrid') }}><option value="research">研究资料库</option><option value="uploaded">上传文档库</option></select></label>
          <label>办事事项<select aria-label="办事事项" value={matterId} disabled={loading || dataset !== 'research'} onChange={(event) => { setMatterId(event.target.value); setFacts({}); setCompletedSteps([]) }}>
            <option value="">全部事项／一般政策问答</option>{research?.matters.map((item) => <option key={item.id} value={item.id}>{item.category} · {item.name}</option>)}
          </select></label>
          <label>适用地域<select aria-label="适用地域" value={region} disabled={loading} onChange={(event) => setRegion(event.target.value)}><option>武汉</option><option>湖北</option><option>全国</option></select></label>
          <label>业务日期<input aria-label="业务日期" type="date" value={asOf} disabled={loading} onChange={(event) => setAsOf(event.target.value)} /></label>
          <label>研究配置<select aria-label="研究配置" value={profile} disabled={loading} onChange={(event) => setProfile(event.target.value)}>
            {!research?.profiles.length && <option value="full">完整方法</option>}{research?.profiles.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select></label>
        </div>
        <p className="muted">三种模式使用所选资料库。因果模式按地域、业务日期和下方事实校验；历史政策只适用于对应时期。</p>
        {researchError && <p className="error-banner">{researchError}</p>}
      </div>
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
                  <button type="button" onClick={() => { setDataset('research'); setMode('causal'); setQuestion('工伤认定申请缺少诊断证明，应当如何补正？') }}>
                    工伤认定缺少材料如何补正？
                  </button>
                  <button type="button" onClick={() => { setDataset('research'); setMode('causal'); setQuestion('养老保险关系转入需要满足什么条件，先办理哪一步？') }}>
                    养老保险关系如何转入？
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
                    <div
                      className={turn.id === selectedTurn?.id ? 'assistant-message selected' : 'assistant-message'}
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelectedTurnId(turn.id)}
                      onKeyDown={(event) => {
                        if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) {
                          event.preventDefault()
                          setSelectedTurnId(turn.id)
                        }
                      }}
                    >
                      <div className="answer-text">
                        <Markdown skipHtml remarkPlugins={[remarkGfm]}>{turn.result.answer}</Markdown>
                      </div>
                      <small>{turn.result.sources.length} 条证据 · 点击查看详情</small>
                    </div>
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
              <button type="button" className={mode === 'causal' ? 'active' : ''} onClick={() => { setDataset('research'); setMode('causal') }}><Network size={14} />规则与因果增强</button>
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
              <button type="submit" aria-label="发送问题" disabled={!question.trim() || loading || (mode === 'causal' && !asOf)}>
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
              {selectedTurn.context && <p className="muted">{selectedTurn.context.dataset === 'research' ? '研究资料库' : '上传文档库'} · {selectedTurn.context.region} · {selectedTurn.context.as_of} · {selectedTurn.context.profile}</p>}
              {!!selectedTurn.result.knowledge_gaps?.length && <details className="research-gap-summary"><summary>资料说明与缺口（{selectedTurn.result.knowledge_gaps.length} 条）</summary><GapList gaps={selectedTurn.result.knowledge_gaps} /></details>}
              {!!selectedTurn.result.rule_checks?.length && <details className="research-gap-summary"><summary>规则校验与路径诊断（{selectedTurn.result.rule_checks.length} 项）</summary><RuleChecks checks={selectedTurn.result.rule_checks} /></details>}
              <CausalPaths paths={selectedTurn.result.causal_paths} />
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
      {dataset === 'research' && matter && <WorkflowPanel key={matter.id} matter={matter} context={context} onFactsChange={setFacts} onCompletedChange={setCompletedSteps} />}
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
