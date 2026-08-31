import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildGraphExport,
  serializeGraphMl,
  truncateGraphLabel,
} from './graphExport.ts'
import type { GraphResponse } from './types.ts'

const graph: GraphResponse = {
  nodes: [
    {
      id: 'node&1',
      label: '数据<安全>',
      type: 'LAW',
      source_chunk_ids: ['chunk&1', 'chunk"2'],
    },
    {
      id: 'node-2',
      label: '安全义务',
      type: 'OBLIGATION',
      source_chunk_ids: ['chunk-3'],
    },
  ],
  edges: [
    {
      id: 'edge&1',
      source: 'node&1',
      target: 'node-2',
      predicate: '规定 & 约束',
      source_chunk_id: 'chunk<4>',
    },
  ],
  truncated: false,
}

test('truncates graph labels after ten Unicode characters', () => {
  assert.equal(truncateGraphLabel('中华人民共和国数据安全法'), '中华人民共和国数据安…')
  assert.equal(truncateGraphLabel('安全义务'), '安全义务')
})

test('builds export data with node colors and current positions', () => {
  assert.deepEqual(
    buildGraphExport(
      graph,
      new Map([
        ['node&1', { x: 12.5, y: 30 }],
        ['node-2', { x: 80, y: 42.25 }],
      ]),
      { LAW: '#245c43', OBLIGATION: '#8d6729' },
      '#56645d',
    ),
    {
      nodes: [
        {
          id: 'node&1',
          label: '数据<安全>',
          type: 'LAW',
          color: '#245c43',
          source_chunk_ids: ['chunk&1', 'chunk"2'],
          position: { x: 12.5, y: 30 },
        },
        {
          id: 'node-2',
          label: '安全义务',
          type: 'OBLIGATION',
          color: '#8d6729',
          source_chunk_ids: ['chunk-3'],
          position: { x: 80, y: 42.25 },
        },
      ],
      edges: graph.edges,
    },
  )
})

test('serializes a directed GraphML document with escaped attributes', () => {
  const data = buildGraphExport(
    graph,
    new Map([
      ['node&1', { x: 12.5, y: 30 }],
      ['node-2', { x: 80, y: 42.25 }],
    ]),
    { LAW: '#245c43', OBLIGATION: '#8d6729' },
    '#56645d',
  )

  const graphMl = serializeGraphMl(data)

  assert.match(graphMl, /<graph id="knowledge-graph" edgedefault="directed">/)
  assert.match(graphMl, /<node id="node&amp;1">/)
  assert.match(graphMl, /<data key="label">数据&lt;安全&gt;<\/data>/)
  assert.ok(graphMl.includes(
    '<data key="source_chunk_ids">[&quot;chunk&amp;1&quot;,&quot;chunk\\&quot;2&quot;]</data>',
  ))
  assert.match(graphMl, /<edge id="edge&amp;1" source="node&amp;1" target="node-2">/)
  assert.match(graphMl, /<data key="predicate">规定 &amp; 约束<\/data>/)
  assert.match(graphMl, /<data key="source_chunk_id">chunk&lt;4&gt;<\/data>/)
})
