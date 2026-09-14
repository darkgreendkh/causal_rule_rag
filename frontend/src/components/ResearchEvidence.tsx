import type { CausalPath, Evidence, RuleCheck } from '../types'

const RESULT_LABELS: Record<string, string> = {
  satisfied: '满足', violated: '不满足', unknown: '信息不足', active: '已启用',
  candidate: '待审核', rejected: '已拒绝', disabled: '已停用', repaired: '找到修复方案',
  already_valid: '无需修复', unreachable: '当前模型内不可达', truncated: '搜索已截断',
  valid: '校验通过', invalid: '存在错误', completed: '已完成', ready: '就绪',
  idle: '尚未构建', building: '构建中', running: '处理中', failed: '失败', pending: '等待处理',
}

export function ResultBadge({ status }: { status: string }) {
  return <span className={`result-badge result-${status}`}>{RESULT_LABELS[status] ?? status}</span>
}

export function EvidenceList({ evidence }: { evidence?: Evidence[] }) {
  return <div className="research-evidence-list">{evidence?.map((item, index) => (
    <details className="research-evidence" key={`${item.unit_id}-${index}`}>
      <summary>{item.title} {item.article}</summary>
      <blockquote>{item.quote}</blockquote>
      <small>{item.source_path} · {item.unit_id}</small>
    </details>
  ))}</div>
}

export function GapList({ gaps }: { gaps?: string[] }) {
  return gaps?.length ? <div className="knowledge-gaps"><strong>资料与适用性说明</strong>
    <ul>{gaps.map((gap, index) => <li key={index}>{gap}</li>)}</ul>
  </div> : null
}

export function RuleChecks({ checks }: { checks?: RuleCheck[] }) {
  return checks?.length ? <section className="research-results"><h3>规则校验</h3>
    {checks.map((check, index) => <div className="rule-check" key={`${check.rule_id}-${index}`}>
      <div><strong>{check.label}</strong><ResultBadge status={check.status} /></div>
      {check.used_for_answer === false && <p className="muted">仅诊断，未用于回答</p>}
      <EvidenceList evidence={check.evidence} />
    </div>)}
  </section> : null
}

export function CausalPaths({ paths }: { paths?: CausalPath[] }) {
  return paths?.length ? <section className="research-results"><h3>有向证据路径</h3>
    {paths.map((path) => <details className="causal-path" key={path.id}>
      <summary>{path.labels.join(' → ')}</summary>
      <p className="score-line">综合 {path.score.toFixed(3)} · 语义 {path.semantic_score.toFixed(3)} · RPC {path.rpc.toFixed(3)} · 熵 {path.entropy.toFixed(3)}</p>
      <p className="muted">{path.edge_ids.length} 跳 · {path.rule_ids.length} 条关联规则</p>
      <EvidenceList evidence={path.evidence} />
    </details>)}
  </section> : null
}
