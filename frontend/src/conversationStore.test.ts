import assert from 'node:assert/strict'
import test from 'node:test'

import {
  LEGACY_STORAGE_KEY,
  STORAGE_KEY,
  appendConversationTurn,
  deleteConversation,
  loadConversationStore,
  renameConversation,
  saveConversationStore,
  selectConversation,
  sortConversations,
  startNewConversation,
} from './conversationStore.ts'
import type { ConversationItem, ConversationStore } from './conversationStore.ts'
import type { QAResponse } from './types.ts'

const result: QAResponse = {
  answer: '应当建立数据安全管理制度。[S1]',
  mode: 'hybrid',
  sources: [],
  graph_paths: [],
}

function turn(id: string, question: string, createdAt: string): ConversationItem {
  return { id, question, createdAt, result }
}

class MemoryStorage {
  private values = new Map<string, string>()

  getItem(key: string): string | null {
    return this.values.get(key) ?? null
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value)
  }

  removeItem(key: string): void {
    this.values.delete(key)
  }
}

test('migrates the existing single conversation without losing turns', () => {
  const storage = new MemoryStorage()
  const legacyTurns = [
    turn('turn-1', '数据处理者有哪些安全义务？', '2026-08-30T09:00:00.000Z'),
    turn('turn-2', '违反上述义务会怎样？', '2026-08-30T09:05:00.000Z'),
  ]
  storage.setItem(LEGACY_STORAGE_KEY, JSON.stringify(legacyTurns))

  const loaded = loadConversationStore(storage, () => 'conversation-1')

  assert.equal(loaded.migratedLegacy, true)
  assert.equal(loaded.store.activeConversationId, 'conversation-1')
  assert.deepEqual(loaded.store.conversations, [
    {
      id: 'conversation-1',
      title: '数据处理者有哪些安全义务？',
      createdAt: '2026-08-30T09:00:00.000Z',
      updatedAt: '2026-08-30T09:05:00.000Z',
      turns: legacyTurns,
    },
  ])

  saveConversationStore(storage, loaded.store, loaded.migratedLegacy)
  assert.notEqual(storage.getItem(STORAGE_KEY), null)
  assert.equal(storage.getItem(LEGACY_STORAGE_KEY), null)
})

test('keeps the legacy value when saving the migrated store fails', () => {
  const storage = new MemoryStorage()
  storage.setItem(LEGACY_STORAGE_KEY, JSON.stringify([
    turn('turn-1', '数据处理者有哪些安全义务？', '2026-08-30T09:00:00.000Z'),
  ]))
  const loaded = loadConversationStore(storage, () => 'conversation-1')
  const failingStorage = {
    ...storage,
    setItem() {
      throw new Error('quota exceeded')
    },
    getItem: storage.getItem.bind(storage),
    removeItem: storage.removeItem.bind(storage),
  }

  assert.throws(
    () => saveConversationStore(failingStorage, loaded.store, loaded.migratedLegacy),
    /quota exceeded/,
  )
  assert.notEqual(storage.getItem(LEGACY_STORAGE_KEY), null)
})

test('ignores malformed stored conversations', () => {
  const storage = new MemoryStorage()
  storage.setItem(STORAGE_KEY, JSON.stringify({ activeConversationId: 3, conversations: 'bad' }))

  assert.deepEqual(loadConversationStore(storage, () => 'unused'), {
    store: { activeConversationId: null, conversations: [] },
    migratedLegacy: false,
  })
})

test('ignores stored conversations with invalid timestamps', () => {
  const storage = new MemoryStorage()
  storage.setItem(STORAGE_KEY, JSON.stringify({
    activeConversationId: 'conversation-1',
    conversations: [{
      id: 'conversation-1',
      title: '数据安全义务',
      createdAt: 'not-a-date',
      updatedAt: 'not-a-date',
      turns: [turn('turn-1', '数据安全义务', 'not-a-date')],
    }],
  }))

  assert.deepEqual(loadConversationStore(storage, () => 'unused'), {
    store: { activeConversationId: null, conversations: [] },
    migratedLegacy: false,
  })
})

test('starts a blank conversation without deleting existing history', () => {
  const existing: ConversationStore = {
    activeConversationId: 'conversation-1',
    conversations: [{
      id: 'conversation-1',
      title: '数据安全义务',
      createdAt: '2026-08-30T09:00:00.000Z',
      updatedAt: '2026-08-30T09:00:00.000Z',
      turns: [turn('turn-1', '数据安全义务', '2026-08-30T09:00:00.000Z')],
    }],
  }

  assert.deepEqual(startNewConversation(existing), {
    activeConversationId: null,
    conversations: existing.conversations,
  })
})

test('creates a titled conversation on the first turn and keeps only its latest twenty turns', () => {
  let store: ConversationStore = { activeConversationId: null, conversations: [] }

  for (let index = 1; index <= 21; index += 1) {
    store = appendConversationTurn(
      store,
      turn(`turn-${index}`, `问题 ${index}`, `2026-08-30T09:${String(index).padStart(2, '0')}:00.000Z`),
      'conversation-1',
    )
  }

  assert.equal(store.activeConversationId, 'conversation-1')
  assert.equal(store.conversations[0].title, '问题 1')
  assert.equal(store.conversations[0].turns.length, 20)
  assert.equal(store.conversations[0].turns[0].id, 'turn-2')
  assert.equal(store.conversations[0].turns[19].id, 'turn-21')
})

test('renames and selects existing conversations', () => {
  const store: ConversationStore = {
    activeConversationId: 'conversation-1',
    conversations: [
      {
        id: 'conversation-1',
        title: '问题一',
        createdAt: '2026-08-30T09:00:00.000Z',
        updatedAt: '2026-08-30T09:00:00.000Z',
        turns: [turn('turn-1', '问题一', '2026-08-30T09:00:00.000Z')],
      },
      {
        id: 'conversation-2',
        title: '问题二',
        createdAt: '2026-08-30T10:00:00.000Z',
        updatedAt: '2026-08-30T10:00:00.000Z',
        turns: [turn('turn-2', '问题二', '2026-08-30T10:00:00.000Z')],
      },
    ],
  }

  const renamed = renameConversation(store, 'conversation-2', '  新标题  ')
  const selected = selectConversation(renamed, 'conversation-2')

  assert.equal(selected.conversations[1].title, '新标题')
  assert.equal(selected.activeConversationId, 'conversation-2')
  assert.equal(renameConversation(selected, 'conversation-2', '   '), selected)
})

test('deletes immediately and falls back to the most recently updated conversation', () => {
  const store: ConversationStore = {
    activeConversationId: 'conversation-1',
    conversations: [
      {
        id: 'conversation-1',
        title: '当前会话',
        createdAt: '2026-08-30T09:00:00.000Z',
        updatedAt: '2026-08-30T09:00:00.000Z',
        turns: [turn('turn-1', '当前会话', '2026-08-30T09:00:00.000Z')],
      },
      {
        id: 'conversation-2',
        title: '较早会话',
        createdAt: '2026-08-30T08:00:00.000Z',
        updatedAt: '2026-08-30T10:00:00.000Z',
        turns: [turn('turn-2', '较早会话', '2026-08-30T08:00:00.000Z')],
      },
      {
        id: 'conversation-3',
        title: '最近会话',
        createdAt: '2026-08-30T11:00:00.000Z',
        updatedAt: '2026-08-30T11:00:00.000Z',
        turns: [turn('turn-3', '最近会话', '2026-08-30T11:00:00.000Z')],
      },
    ],
  }

  const deleted = deleteConversation(store, 'conversation-1')

  assert.deepEqual(deleted.conversations.map((conversation) => conversation.id), [
    'conversation-2',
    'conversation-3',
  ])
  assert.equal(deleted.activeConversationId, 'conversation-3')
  assert.deepEqual(sortConversations(deleted.conversations).map((conversation) => conversation.id), [
    'conversation-3',
    'conversation-2',
  ])
})
