import { ArrowDown, ArrowUp, Check, Plus, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { checkWorkflow, listActions, nextWorkflow, repairWorkflow } from '../api'
import type { Facts, Matter, MatterField, NextCandidate, ResearchAction, ResearchContext, WorkflowCheck, WorkflowNext, WorkflowRepair, WorkflowRequest } from '../types'
import { applySimulation, collectFacts } from '../workflowForm'
import { EvidenceList, GapList, ResultBadge, RuleChecks } from './ResearchEvidence'

export default function WorkflowPanel({ matter, context, onFactsChange, onCompletedChange }: { matter: Matter; context: ResearchContext; onFactsChange: (facts: Facts) => void; onCompletedChange: (steps: string[]) => void }) {
  const [actions, setActions] = useState<ResearchAction[]>([])
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({})
  const [steps, setSteps] = useState<string[]>([])
  const [completed, setCompleted] = useState<string[]>([])
  const [actionId, setActionId] = useState('')
  const [goal, setGoal] = useState(matter.goals[0]?.id ?? '')
  const [check, setCheck] = useState<WorkflowCheck | null>(null)
  const [repair, setRepair] = useState<WorkflowRepair | null>(null)
  const [next, setNext] = useState<WorkflowNext | null>(null)
  const [preview, setPreview] = useState<NextCandidate | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [historyDraft, setHistoryDraft] = useState(false)
  const facts = useMemo(() => collectFacts(matter.fields, inputs, confirmed), [matter.fields, inputs, confirmed])
  useEffect(() => { onFactsChange(facts) }, [facts, onFactsChange])
  useEffect(() => { onCompletedChange(completed) }, [completed, onCompletedChange])
  const request: WorkflowRequest = { region: context.region, as_of: context.as_of, profile: context.profile, matter_id: matter.id, facts, steps, completed_steps: completed, goal }
  const requestKey = JSON.stringify(request)
  const [resultKey, setResultKey] = useState('')
  const resultsCurrent = resultKey === requestKey

  useEffect(() => {
    let active = true
    void listActions(matter.id).then((items) => { if (active) { setActions(items); setActionId(items[0]?.id ?? '') } })
      .catch((err: unknown) => { if (active) setError(err instanceof Error ? err.message : '操作列表加载失败') })
    return () => { active = false }
  }, [matter.id])

  async function run(kind: 'check' | 'repair' | 'next') {
    setBusy(true)
    setError('')
    setPreview(null)
    setCheck(null)
    setRepair(null)
    setNext(null)
    try {
      if (kind === 'check') setCheck(await checkWorkflow(request))
      if (kind === 'repair') setRepair(await repairWorkflow(request))
      if (kind === 'next') setNext(await nextWorkflow({ ...request, steps: [] }))
      setResultKey(requestKey)
    } catch (err) { setError(err instanceof Error ? err.message : '流程校验失败') }
    finally { setBusy(false) }
  }

  function applyPreview() {
    if (!preview || !resultsCurrent) return
    const updated = applySimulation(matter.fields, facts, completed, preview)
    setInputs(Object.fromEntries(Object.entries(updated.facts).map(([id, value]) => [id, Array.isArray(value) ? value.join(',') : String(value)])))
    setCompleted(updated.completed_steps)
    setSteps((current) => current[0] === preview.action_id ? current.slice(1) : current)
    setPreview(null)
  }

  function reorder(index: number, direction: number) {
    setSteps((current) => {
      const updated = [...current]
      ;[updated[index], updated[index + direction]] = [updated[index + direction], updated[index]]
      return updated
    })
  }

  function restart() {
    setInputs({}); setConfirmed({}); setCompleted([]); setSteps([]); setCheck(null); setRepair(null); setNext(null); setPreview(null); setError('')
  }

  const actionLabel = (id: string) => actions.find((action) => action.id === id)?.label ?? id
  return <section className="panel workflow-panel">
    <div className="section-heading"><div><h2>审批流程校验与修复</h2><p className="muted">{matter.name} · 操作只推进本地模拟，外部审核结果需明确提供。</p></div>
      <button className="secondary-button" onClick={restart} disabled={busy}>新建模拟</button>
    </div>
    <GapList gaps={matter.gaps} />
    <fieldset disabled={busy} className="workflow-fields"><legend>申请事实与政策参数</legend>
      {matter.fields.map((field) => <div className={`workflow-field field-${field.role}`} key={field.id}>
        <label htmlFor={`workflow-${field.id}`}>{field.label}{field.unit ? `（${field.unit}）` : ''}
          <small>{field.role === 'policy' ? '政策参数 · 只读' : field.role === 'external' ? '外部确认' : field.mutable === false ? '事实不可由修复改变' : '申请信息'}</small>
        </label>
        {field.role === 'policy' ? <output id={`workflow-${field.id}`}>{displayValue(matter.policy_parameters[field.id])}</output> : <>
          <FieldInput field={field} value={inputs[field.id] ?? ''} locked={completed.length > 0 && field.mutable === false && field.role !== 'external'} onChange={(value) => setInputs((current) => ({ ...current, [field.id]: value }))} />
          {field.role === 'external' && <label className="external-confirm"><input type="checkbox" checked={!!confirmed[field.id]} onChange={(event) => setConfirmed((current) => ({ ...current, [field.id]: event.target.checked }))} />已核对此项外部结果</label>}
        </>}
      </div>)}
      {!matter.fields.length && <p className="muted">该事项尚无可执行字段，请核对上述资料缺口。</p>}
    </fieldset>
    <div className="workflow-columns">
      <section><h3>已办历史</h3><p className="muted">已记录的操作不能在当前模拟中撤销。</p>
        <ol className="workflow-steps completed-steps">{completed.map((id, index) => <li key={`${id}-${index}`}><Check size={14} /><span>{actionLabel(id)}</span></li>)}</ol>
        {!completed.length && <p className="muted">尚未记录已办步骤。</p>}
        <details><summary>记录已有办理历史</summary><p className="muted">请只记录实际已完成的步骤；外部操作还须在上方确认相应结果。</p>
          <label className="external-confirm"><input type="checkbox" checked={historyDraft} onChange={(event) => setHistoryDraft(event.target.checked)} />所选步骤已完成</label>
          <select value={actionId} aria-label="已有历史步骤" onChange={(event) => setActionId(event.target.value)} disabled={busy}>{actions.map((action) => <option key={action.id} value={action.id}>{action.label}{action.kind === 'external' ? '（外部）' : ''}</option>)}</select>
          <button className="secondary-button" disabled={busy || !historyDraft || !actionId} onClick={() => { setCompleted((current) => [...current, actionId]); setHistoryDraft(false) }}>记录为已办</button>
        </details>
      </section>
      <section><h3>拟执行步骤</h3><ol className="workflow-steps">{steps.map((id, index) => <li key={`${id}-${index}`}><span>{index + 1}. {actionLabel(id)}</span>
        <button className="icon-button" aria-label={`上移第 ${index + 1} 步`} disabled={busy || index === 0} onClick={() => reorder(index, -1)}><ArrowUp size={14} /></button>
        <button className="icon-button" aria-label={`下移第 ${index + 1} 步`} disabled={busy || index === steps.length - 1} onClick={() => reorder(index, 1)}><ArrowDown size={14} /></button>
        <button className="icon-button" aria-label={`删除第 ${index + 1} 步`} disabled={busy} onClick={() => setSteps((current) => current.filter((_, position) => position !== index))}><Trash2 size={14} /></button>
      </li>)}</ol>
        <div className="research-toolbar"><select aria-label="添加计划步骤" value={actionId} disabled={busy} onChange={(event) => setActionId(event.target.value)}>{actions.map((action) => <option key={action.id} value={action.id}>{action.label}{action.kind === 'external' ? '（外部）' : ''}</option>)}</select>
          <button className="secondary-button" disabled={busy || !actionId} onClick={() => setSteps((current) => [...current, actionId])}><Plus size={14} />添加</button>
        </div>
      </section>
    </div>
    <div className="research-toolbar">
      <label>目标<select aria-label="目标" value={goal} disabled={busy} onChange={(event) => setGoal(event.target.value)}><option value="">未选择目标</option>{matter.goals.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
      <button className="primary-button" disabled={busy || !matter.capabilities.checkable} onClick={() => void run('check')}>校验条件与计划</button>
      <button className="secondary-button" disabled={busy || !goal || !matter.capabilities.repairable} onClick={() => void run('repair')}>寻找最小修复</button>
      <button className="secondary-button" disabled={busy || !matter.capabilities.simulatable} onClick={() => void run('next')}>查看当前下一步</button>
    </div>
    {busy && <p className="muted" aria-live="polite">正在计算…</p>}{error && <p className="error-banner">{error}</p>}
    {(check || repair || next) && !resultsCurrent && <p className="notice-banner">输入或步骤已变化，请重新校验后再应用方案。</p>}
    {check && <CheckResult result={check} fields={matter.fields} />}
    {repair && <div className="workflow-result"><h3>修复预览 <ResultBadge status={repair.status} /></h3>
      <p className="muted">候选动作和当前搜索范围内的修复；成本 {repair.cost ?? '未确定'}，探索 {repair.explored_states} 个状态。</p>
      {repair.truncated && <p className="notice-banner">搜索已达到上限，尚不能确认存在最小可行修复。</p>}
      <ol>{repair.steps.map((id, index) => <li key={`${id}-${index}`}>{actionLabel(id)}</li>)}</ol>
      {repair.edits.length > 0 && <details><summary>修改明细</summary><pre className="research-json">{JSON.stringify(repair.edits, null, 2)}</pre></details>}
      {repair.checked && <CheckResult result={repair.checked} fields={matter.fields} />}
      <button className="secondary-button" disabled={busy || !resultsCurrent || repair.status !== 'repaired' || repair.truncated} onClick={() => { setSteps(repair.steps); setPreview(null) }}>采用为拟执行步骤</button>
    </div>}
    {next && <div className="workflow-result"><h3>当前可选操作 <ResultBadge status={next.status} /></h3>
      {!next.candidates.length && <p className="muted">当前没有可推荐的操作。</p>}
      {next.candidates.map((candidate) => <div className="next-candidate" key={candidate.action_id}>
        <div><strong>{candidate.label}</strong><ResultBadge status={candidate.status} /><button className="secondary-button" disabled={busy || !resultsCurrent} onClick={() => setPreview(candidate)}>预览</button></div>
        {candidate.missing_fields.length > 0 && <p className="muted">待提供：{candidate.missing_fields.map((id) => matter.fields.find((field) => field.id === id)?.label ?? id).join('、')}</p>}
        <EvidenceList evidence={candidate.evidence} />
      </div>)}
    </div>}
    {preview && resultsCurrent && <div className="simulation-preview"><h3>{preview.label} · 应用预览</h3><dl>
      {Object.entries(preview.preview_state ?? {}).filter(([id, value]) => JSON.stringify(facts[id]) !== JSON.stringify(value) && matter.fields.some((field) => field.id === id && field.role === 'applicant' && field.mutable !== false)).map(([id, value]) => <div key={id}><dt>{matter.fields.find((field) => field.id === id)?.label ?? id}</dt><dd>{displayValue(facts[id])} → {displayValue(value)}</dd></div>)}
      <div><dt>新增已办步骤</dt><dd>{preview.label}</dd></div>
    </dl>{!preview.preview_state && <p className="notice-banner">操作条件尚未满足，当前没有可应用的状态。</p>}<button className="primary-button" disabled={preview.status !== 'satisfied' || !preview.preview_state || busy} onClick={applyPreview}>应用到当前模拟</button></div>}
  </section>
}

function FieldInput({ field, value, locked, onChange }: { field: MatterField; value: string; locked: boolean; onChange: (value: string) => void }) {
  const id = `workflow-${field.id}`
  if (field.type === 'boolean' || field.type === 'enum') return <select id={id} value={value} disabled={locked} onChange={(event) => onChange(event.target.value)}>
    <option value="">未知／尚未提供</option>{field.type === 'boolean' ? <><option value="true">是</option><option value="false">否</option></> : field.options?.map((option) => <option key={option}>{option}</option>)}
  </select>
  return <input id={id} type={field.type === 'number' ? 'number' : field.type === 'date' ? 'date' : 'text'} step={field.type === 'number' ? 'any' : undefined} value={value} disabled={locked} placeholder={field.type === 'set' ? '多个值用逗号分隔；留空表示未知' : '留空表示未知'} onChange={(event) => onChange(event.target.value)} />
}

function displayValue(value: unknown) {
  if (value === undefined || value === null) return '未知'
  if (typeof value === 'boolean') return value ? '是' : '否'
  return Array.isArray(value) ? value.join('、') : typeof value === 'object' ? JSON.stringify(value) : String(value)
}

function CheckResult({ result, fields }: { result: WorkflowCheck; fields: MatterField[] }) {
  const labels = (ids: string[]) => ids.map((id) => fields.find((field) => field.id === id)?.label ?? id).join('、')
  return <div className="workflow-result"><h3>校验结果 <ResultBadge status={result.status} /></h3>
    <p className="muted">目标状态：{result.goal_satisfied === true || result.goal_satisfied === 'satisfied' ? '已满足' : result.goal_satisfied === false || result.goal_satisfied === 'violated' ? '尚未满足' : '待补充信息'}</p>
    {result.first_error && <p className="error-banner">{result.first_error.kind === 'goal' ? '目标状态' : result.first_error.index < 0 ? '初始条件' : `${result.first_error.kind === 'history' ? '已办历史' : '计划'}第 ${result.first_error.index + 1} 步`}：{result.first_error.message}</p>}
    {!!result.missing_fields.length && <p className="notice-banner">待提供：{labels(result.missing_fields)}</p>}
    <GapList gaps={result.knowledge_gaps} /><RuleChecks checks={result.checks} />
    <details><summary>预计状态</summary><dl className="state-list">{Object.entries(result.state as Facts).map(([id, value]) => <div key={id}><dt>{labels([id])}</dt><dd>{displayValue(value)}</dd></div>)}</dl></details>
  </div>
}
