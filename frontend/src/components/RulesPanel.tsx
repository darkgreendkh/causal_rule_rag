import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { loadResearchSummary, listRules, reviewRules } from '../api'
import type { Matter, ResearchRule, ResearchSummary, RuleStatus } from '../types'
import { EvidenceList, ResultBadge } from './ResearchEvidence'

export default function RulesPanel({ revision = 0 }: { revision?: number }) {
  const [matters, setMatters] = useState<Matter[]>([])
  const [matterId, setMatterId] = useState('')
  const [documents, setDocuments] = useState<ResearchSummary['documents']>([])
  const [sourcePath, setSourcePath] = useState('')
  const [status, setStatus] = useState<RuleStatus | ''>('')
  const [search, setSearch] = useState('')
  const [rules, setRules] = useState<ResearchRule[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const fetchVersion = useRef(0)
  const refresh = useCallback(async () => {
    const version = ++fetchVersion.current
    try { const items = await listRules(matterId, status); if (version === fetchVersion.current) { setRules(items); setSelected(new Set()); setError('') } }
    catch (err) { if (version === fetchVersion.current) setError(err instanceof Error ? err.message : '规则加载失败') }
  }, [matterId, status])
  useEffect(() => { void loadResearchSummary().then((data) => { setMatters(data.matters); setDocuments(data.documents) }).catch((err: unknown) => setError(err instanceof Error ? err.message : '事项加载失败')) }, [revision])
  useEffect(() => { void refresh() }, [refresh, revision])
  const visible = useMemo(() => rules.filter((rule) => rule.label.includes(search.trim()) && (!sourcePath || rule.evidence.some((item) => item.source_path === sourcePath))), [rules, search, sourcePath])
  async function review(action: 'activate' | 'reject' | 'disable') {
    setBusy(true)
    setMessage('')
    try {
      const result = await reviewRules([...selected], action)
      await refresh()
      const failures = result.results.filter((item) => item.error)
      setMessage(`已处理 ${result.results.length - failures.length} 条规则。${failures.map((item) => `${item.id}：${item.error}`).join('；')}`)
    } catch (err) { setError(err instanceof Error ? err.message : '批量审核失败') }
    finally { setBusy(false) }
  }
  return <section className="panel rules-panel">
    <div className="section-heading"><div><h2>规则审核与依据</h2><p className="muted">核对条件和来源后可按事项批量启用；模型新增规则保留为候选。</p></div></div>
    {error && <p className="error-banner">{error}</p>}{message && <p className="notice-banner">{message}</p>}
    <div className="research-toolbar">
      <select aria-label="规则来源文档" value={sourcePath} onChange={(event) => { setSourcePath(event.target.value); setSelected(new Set()) }} disabled={busy}>
        <option value="">全部来源文档</option>{documents.map((document) => <option key={document.id} value={document.source_path}>{document.filename}</option>)}
      </select>
      <select aria-label="规则所属事项" value={matterId} onChange={(event) => setMatterId(event.target.value)} disabled={busy}>
        <option value="">全部事项</option>{matters.map((matter) => <option key={matter.id} value={matter.id}>{matter.name}</option>)}
      </select>
      <select aria-label="规则状态" value={status} onChange={(event) => setStatus(event.target.value as RuleStatus | '')} disabled={busy}>
        <option value="">全部状态</option><option value="candidate">待审核</option><option value="active">已启用</option><option value="rejected">已拒绝</option><option value="disabled">已停用</option>
      </select>
      <input type="search" aria-label="搜索规则" placeholder="搜索规则" value={search} onChange={(event) => { setSearch(event.target.value); setSelected(new Set()) }} />
      <button className="secondary-button" onClick={() => void refresh()} disabled={busy}>刷新</button>
    </div>
    <div className="research-toolbar rule-batch">
      <label><input type="checkbox" checked={visible.length > 0 && visible.every((rule) => selected.has(rule.id))} disabled={busy} onChange={(event) => setSelected(event.target.checked ? new Set(visible.map((rule) => rule.id)) : new Set())} />选择当前 {visible.length} 条</label>
      <span>{selected.size} 条已选</span>
      <button className="primary-button" disabled={busy || !selected.size} onClick={() => void review('activate')}>批量启用</button>
      <button className="secondary-button" disabled={busy || !selected.size} onClick={() => void review('reject')}>拒绝</button>
      <button className="secondary-button" disabled={busy || !selected.size} onClick={() => void review('disable')}>停用</button>
    </div>
    <div className="rules-list">{visible.map((rule) => <article className="research-rule" key={rule.id}>
      <label className="rule-selection"><input type="checkbox" aria-label={`选择规则 ${rule.label}`} checked={selected.has(rule.id)} disabled={busy} onChange={(event) => setSelected((current) => { const next = new Set(current); if (event.target.checked) next.add(rule.id); else next.delete(rule.id); return next })} /></label>
      <details><summary><strong>{rule.label}</strong><ResultBadge status={rule.status} /></summary>
        <p className="muted">{rule.scope.region} · {rule.scope.valid_from ?? '起始日期未知'} 至 {rule.scope.valid_to ?? '结束日期未载明'} · {rule.scope.validity_known ? '已记录适用期' : '适用期待核对'}</p>
        <p className="muted">核对来源：{rule.review_source === 'implementation_source_review' ? '实现者对照原文核对' : rule.review_source || '尚未审核'}</p>
        {rule.validation_errors.length > 0 && <p className="error-banner">{rule.validation_errors.join('；')}</p>}
        <EvidenceList evidence={rule.evidence} />
        <details><summary>结构化规则</summary><pre className="research-json">{JSON.stringify(rule.condition, null, 2)}</pre></details>
      </details>
    </article>)}</div>
    {!visible.length && <p className="muted">当前筛选下没有规则。</p>}
  </section>
}
