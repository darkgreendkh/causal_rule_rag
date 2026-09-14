import { useEffect, useState } from 'react'
import { extractCandidateRules, listResearchUnits, loadResearchSummary, removeResearchDocument } from '../api'
import type { ResearchSummary, ResearchUnit } from '../types'

export default function ResearchDocuments({ onResearchChange }: { onResearchChange: () => void }) {
  const [summary, setSummary] = useState<ResearchSummary | null>(null)
  const [documentId, setDocumentId] = useState('')
  const [units, setUnits] = useState<ResearchUnit[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [removing, setRemoving] = useState(false)
  const [matterId, setMatterId] = useState('')
  const [extractingUnit, setExtractingUnit] = useState('')
  const [message, setMessage] = useState('')
  useEffect(() => { void loadResearchSummary().then(setSummary).catch((err: unknown) => setError(err instanceof Error ? err.message : '原始资料加载失败')) }, [])
  useEffect(() => {
    if (!documentId) { setUnits([]); return }
    let active = true
    setLoading(true)
    void listResearchUnits(documentId).then((items) => { if (active) { setUnits(items); setError('') } })
      .catch((err: unknown) => { if (active) { setUnits([]); setError(err instanceof Error ? err.message : '条款加载失败') } })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [documentId])
  const selected = summary?.documents.find((item) => item.id === documentId)
  const matters = summary?.matters.filter((matter) => units.some((unit) => matter.source_unit_ids.includes(unit.id))) ?? []
  const matter = matters.find((item) => item.id === matterId)
  async function removeSelected() {
    if (!selected || !window.confirm(`将“${selected.filename}”移出研究知识库？原始文件会保留，关联规则和图谱将同步失效。`)) return
    setRemoving(true)
    try { await removeResearchDocument(selected.id); setDocumentId(''); setSummary(await loadResearchSummary()); setError(''); setMessage(''); onResearchChange() }
    catch (err) { setError(err instanceof Error ? err.message : '移出知识库失败') }
    finally { setRemoving(false) }
  }
  async function extract(unit: ResearchUnit) {
    if (!matter?.source_unit_ids.includes(unit.id)) return
    setExtractingUnit(unit.id)
    setMessage('')
    setError('')
    try {
      const result = await extractCandidateRules(matter.id, unit.id)
      const invalid = result.rules.filter((rule) => rule.validation_errors.length).length
      setMessage(`已生成 ${result.rules.length} 条候选规则${invalid ? `，其中 ${invalid} 条有校验问题` : ''}。请在下方规则区核对来源与条件后启用。`)
      onResearchChange()
    } catch (err) { setError(err instanceof Error ? err.message : '候选规则抽取失败') }
    finally { setExtractingUnit('') }
  }
  return <section className="panel research-documents"><h2>数据集原始政策</h2><p className="muted">研究资料直接来自 data 文件夹，按独立法规与条款展示。</p>
    {error && <p className="error-banner">{error}</p>}
    {message && <p className="notice-banner">{message}</p>}
    <div className="research-toolbar"><select aria-label="数据集政策文档" value={documentId} disabled={removing || !!extractingUnit} onChange={(event) => { setDocumentId(event.target.value); setMatterId(''); setMessage('') }}>
      <option value="">选择原始政策（{summary?.documents.length ?? 0} 份）</option>{summary?.documents.map((item) => <option value={item.id} key={item.id}>{item.category} · {item.filename}</option>)}
    </select>{selected && <button className="secondary-button" disabled={removing || !!extractingUnit} onClick={() => void removeSelected()}>{removing ? '正在移出…' : '移出知识库'}</button>}</div>
    {selected && <p className="muted">{selected.source_path} · {selected.unit_count} 个单元{selected.source_url && /^https?:\/\//.test(selected.source_url) && <> · <a href={selected.source_url} target="_blank" rel="noreferrer">原始来源网页</a></>}</p>}
    {selected && <div className="research-toolbar"><select aria-label="候选抽取所属事项" value={matterId} disabled={loading || !!extractingUnit} onChange={(event) => setMatterId(event.target.value)}>
      <option value="">选择事项以抽取候选规则</option>{matters.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
    </select><span className="muted">每次抽取当前条款，生成的规则均需审核。</span></div>}
    {loading ? <p className="muted">正在读取原文…</p> : <div className="research-source-units">{units.map((unit) => <details key={unit.id}>
      <summary>{unit.title} · {unit.article || '正文'}</summary>
      <p className="muted">{unit.region} · {unit.valid_from ?? '起始日期未知'} 至 {unit.valid_to ?? '结束日期未载明'} · {unit.validity_known ? '已记录适用期' : '适用期待核对'}</p>
      <pre>{unit.text}</pre><small className="muted">{unit.id}</small>
      {matter && <div className="research-toolbar"><button className="secondary-button" disabled={!!extractingUnit || !matter.source_unit_ids.includes(unit.id)} onClick={() => void extract(unit)}>{extractingUnit === unit.id ? '正在抽取候选…' : '从当前条款抽取候选'}</button>{!matter.source_unit_ids.includes(unit.id) && <small className="muted">该条款不属于所选事项。</small>}</div>}
    </details>)}</div>}
  </section>
}
