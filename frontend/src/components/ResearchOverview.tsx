import { useCallback, useEffect, useState } from 'react'
import { buildResearch, loadCoverage, loadResearchStatus, loadResearchSummary } from '../api'
import type { Coverage, ResearchStatus, ResearchSummary } from '../types'
import { GapList, ResultBadge } from './ResearchEvidence'

const COUNT_LABELS: Record<string, string> = {
  documents: '政策文档', units: '语义单元', matters: '办事事项', rules: '规则', actions: '操作',
  references: '研究文献', nodes: '全库节点', edges: '全库关系', communities: '社区',
  active_rules: '已启用规则', candidate_rules: '待审核规则', coverage: '覆盖记录',
  policy_documents: '政策文档', reference_documents: '研究文献', reference_pages: '文献页数', covered_units: '覆盖单元',
}

export default function ResearchOverview() {
  const [summary, setSummary] = useState<ResearchSummary | null>(null)
  const [status, setStatus] = useState<ResearchStatus | null>(null)
  const [profile, setProfile] = useState('full')
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [error, setError] = useState('')
  const [building, setBuilding] = useState(false)
  const [coverage, setCoverage] = useState<Coverage[] | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [data, progress] = await Promise.all([loadResearchSummary(), loadResearchStatus()])
      setSummary(data)
      setStatus(progress)
      setError('')
    } catch (err) { setError(err instanceof Error ? err.message : '研究知识库加载失败') }
  }, [])

  useEffect(() => { void refresh() }, [refresh])
  const active = building || !!status && ['pending', 'building', 'running'].includes(status.status.toLowerCase())
  useEffect(() => {
    if (!active) return
    const timer = window.setInterval(() => void refresh(), 3000)
    return () => window.clearInterval(timer)
  }, [active, refresh])

  async function build() {
    setBuilding(true)
    setError('')
    try { setStatus(await buildResearch(profile)); await refresh() }
    catch (err) { setError(err instanceof Error ? err.message : '知识库构建失败') }
    finally { setBuilding(false) }
  }

  const matters = summary?.matters.filter((matter) => (!category || matter.category === category) &&
    `${matter.name} ${matter.description}`.includes(search.trim())) ?? []

  return <section className="panel research-overview">
    <div className="section-heading"><div><h2>论文研究知识库</h2><p className="muted">全库统计、办事事项目录与政策依据覆盖</p></div>
      <button className="secondary-button" onClick={() => void refresh()}>刷新</button>
    </div>
    {error && <p className="error-banner">{error}</p>}
    <div className="research-toolbar">
      <label>研究配置<select value={profile} onChange={(event) => setProfile(event.target.value)} disabled={active}>
        {!summary?.profiles.length && <option value="full">完整方法</option>}
        {summary?.profiles.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
      </select></label>
      <button className="primary-button" disabled={active} onClick={() => void build()}>{active ? '构建中…' : '构建研究知识库'}</button>
      {status && <div className="build-status"><ResultBadge status={status.status} /><span>{status.stage}</span></div>}
    </div>
    <p className="muted">{summary?.profiles.find((item) => item.id === profile)?.description}</p>
    {status?.error && <p className="error-banner">{status.error}</p>}
    {summary?.build_id && <small className="muted">知识版本：{summary.build_id}</small>}
    <div className="research-counts">{Object.entries(summary?.counts ?? {}).map(([key, value]) =>
      <div key={key}><strong>{value}</strong><span>{COUNT_LABELS[key] ?? key}</span></div>)}</div>
    {!!summary?.gaps.length && <details className="research-gap-summary"><summary>全库资料说明与缺口（{summary.gaps.length} 条，展开查看）</summary><GapList gaps={summary.gaps} /></details>}
    <div className="research-toolbar">
      <input aria-label="搜索办事事项" type="search" placeholder="搜索办事事项" value={search} onChange={(event) => setSearch(event.target.value)} />
      <select aria-label="事项分类" value={category} onChange={(event) => setCategory(event.target.value)}>
        <option value="">全部分类</option>{[...new Set(summary?.matters.map((matter) => matter.category))].sort().map((item) => <option key={item}>{item}</option>)}
      </select><span className="muted">{matters.length} 个事项</span>
    </div>
    <div className="matter-catalog">{matters.map((matter) => <details className="matter-row" key={matter.id}>
      <summary><strong>{matter.name}</strong><span>{matter.category}</span>
        <span className="capability-tags">{matter.capabilities.checkable && <i>条件校验</i>}{matter.capabilities.simulatable && <i>流程模拟</i>}{matter.capabilities.repairable && <i>修复</i>}{!matter.capabilities.simulatable && <i className="capability-limited">流程待完善</i>}</span>
      </summary><p>{matter.description}</p><GapList gaps={matter.gaps} />
      <p className="muted">{matter.rule_ids.length} 条规则 · {matter.action_ids.length} 个操作 · {matter.source_unit_ids.length} 条来源</p>
    </details>)}</div>
    {summary && !summary.matters.length && <p className="muted">尚未构建研究知识库。构建完成后显示实际事项目录。</p>}
    <details className="coverage-detail" onToggle={(event) => {
      if (event.currentTarget.open && coverage === null) void loadCoverage().then(setCoverage).catch((err: unknown) => setError(err instanceof Error ? err.message : '覆盖记录加载失败'))
    }}><summary>查看条款覆盖与排除依据</summary>
      {coverage?.map((item) => <div key={item.unit_id}><code>{item.unit_id}</code><span>{item.disposition === 'mapped' ? `关联 ${item.matter_ids.length} 个事项` : '排除'}</span><p>{item.reason}</p></div>)}
    </details>
  </section>
}
