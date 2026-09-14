import type { Facts, MatterField, NextCandidate } from './types'

export function parseFieldValue(field: MatterField, raw: string): unknown {
  if (!raw.trim()) return undefined
  if (field.type === 'boolean') return raw === 'true' ? true : raw === 'false' ? false : undefined
  if (field.type === 'number') {
    const value = Number(raw)
    return Number.isFinite(value) ? value : undefined
  }
  if (field.type === 'set') return raw.split(/[,，\n]/).map((item) => item.trim()).filter(Boolean)
  return raw.trim()
}

export function collectFacts(
  fields: MatterField[], input: Record<string, string>, confirmed: Record<string, boolean>,
): Facts {
  const facts: Facts = {}
  for (const field of fields) {
    if (field.role === 'policy' || (field.role === 'external' && !confirmed[field.id])) continue
    const value = parseFieldValue(field, input[field.id] ?? '')
    if (value !== undefined) facts[field.id] = value
  }
  return facts
}

export function applySimulation(
  fields: MatterField[], facts: Facts, completed: string[], candidate: NextCandidate,
): { facts: Facts; completed_steps: string[] } {
  if (candidate.status !== 'satisfied' || !candidate.preview_state) throw new Error('只有校验满足且有预览状态的操作才能应用')
  const updated = { ...facts }
  for (const field of fields) {
    if (field.role === 'applicant' && field.mutable !== false && field.id in candidate.preview_state) {
      updated[field.id] = candidate.preview_state[field.id]
    }
  }
  return { facts: updated, completed_steps: [...completed, candidate.action_id] }
}
