import assert from 'node:assert/strict'
import test from 'node:test'

import { applySimulation, collectFacts, parseFieldValue } from './workflowForm.ts'
import type { MatterField, NextCandidate } from './types.ts'

const fields: MatterField[] = [
  { id: 'has_material', label: '材料', type: 'boolean', role: 'applicant', mutable: true },
  { id: 'age', label: '年龄', type: 'number', role: 'applicant', mutable: false },
  { id: 'threshold', label: '政策阈值', type: 'number', role: 'policy' },
  { id: 'approved', label: '审核结果', type: 'boolean', role: 'external' },
]

test('unknown booleans and empty numbers remain absent instead of false or zero', () => {
  assert.equal(parseFieldValue(fields[0], ''), undefined)
  assert.equal(parseFieldValue(fields[0], 'false'), false)
  assert.equal(parseFieldValue(fields[1], ''), undefined)
  assert.equal(parseFieldValue(fields[1], '0'), 0)
})

test('facts exclude policy values and unconfirmed external results', () => {
  const input = { has_material: 'false', age: '28', threshold: '1', approved: 'true' }
  assert.deepEqual(collectFacts(fields, input, {}), { has_material: false, age: 28 })
  assert.deepEqual(collectFacts(fields, input, { approved: true }), {
    has_material: false, age: 28, approved: true,
  })
})

test('simulation preserves immutable facts, external decisions and completed history', () => {
  const candidate: NextCandidate = {
    action_id: 'submit', label: '提交', status: 'satisfied', missing_fields: [], evidence: [],
    preview_state: { has_material: true, age: 18, threshold: 0, approved: true },
  }
  assert.deepEqual(applySimulation(fields, { has_material: false, age: 28 }, ['registered'], candidate), {
    facts: { has_material: true, age: 28 }, completed_steps: ['registered', 'submit'],
  })
  assert.throws(() => applySimulation(fields, {}, [], { ...candidate, status: 'unknown' }))
})
