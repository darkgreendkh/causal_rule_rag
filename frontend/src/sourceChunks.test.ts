import assert from 'node:assert/strict'
import test from 'node:test'

import { formatSourceChunk, groupSourceChunks } from './sourceChunks.ts'

test('groups source chunks by document filename and sorts their indexes', () => {
  assert.deepEqual(
    groupSourceChunks(
      ['document-1:6', 'document-2:3', 'document-1:5'],
      [
        { id: 'document-1', filename: '行政法规.md' },
        { id: 'document-2', filename: '数据安全法.md' },
      ],
    ),
    [
      { documentId: 'document-1', filename: '行政法规.md', chunkIndexes: [5, 6] },
      { documentId: 'document-2', filename: '数据安全法.md', chunkIndexes: [3] },
    ],
  )
})

test('formats a source chunk with its document filename', () => {
  assert.equal(
    formatSourceChunk('document-1:2', [{ id: 'document-1', filename: '行政法规.md' }]),
    '行政法规.md · 分块 2',
  )
})
