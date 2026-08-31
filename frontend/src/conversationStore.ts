import type { QAResponse } from './types'

export const LEGACY_STORAGE_KEY = 'causal-rule-rag:conversation:v1'
export const STORAGE_KEY = 'causal-rule-rag:conversations:v2'
export const MAX_STORED_TURNS = 20

export interface ConversationItem {
  id: string
  question: string
  createdAt: string
  result: QAResponse
}

export interface Conversation {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  turns: ConversationItem[]
}

export interface ConversationStore {
  activeConversationId: string | null
  conversations: Conversation[]
}

interface StorageReader {
  getItem(key: string): string | null
}

interface StorageWriter {
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

interface LoadedConversationStore {
  store: ConversationStore
  migratedLegacy: boolean
}

const EMPTY_STORE: ConversationStore = {
  activeConversationId: null,
  conversations: [],
}

export function loadConversationStore(
  storage: StorageReader,
  createId: () => string,
): LoadedConversationStore {
  const current = parseStoredValue(storage.getItem(STORAGE_KEY))
  if (isConversationStore(current)) {
    return { store: current, migratedLegacy: false }
  }

  const legacy = parseStoredValue(storage.getItem(LEGACY_STORAGE_KEY))
  if (!Array.isArray(legacy) || legacy.length === 0 || !legacy.every(isConversationItem)) {
    return { store: EMPTY_STORE, migratedLegacy: false }
  }

  const turns = legacy.slice(-MAX_STORED_TURNS)
  const conversation: Conversation = {
    id: createId(),
    title: turns[0].question,
    createdAt: turns[0].createdAt,
    updatedAt: turns[turns.length - 1].createdAt,
    turns,
  }
  return {
    store: {
      activeConversationId: conversation.id,
      conversations: [conversation],
    },
    migratedLegacy: true,
  }
}

export function saveConversationStore(
  storage: StorageWriter,
  store: ConversationStore,
  removeLegacy: boolean,
): void {
  if (store.conversations.length === 0) {
    storage.removeItem(STORAGE_KEY)
  } else {
    storage.setItem(STORAGE_KEY, JSON.stringify(store))
  }
  if (removeLegacy) storage.removeItem(LEGACY_STORAGE_KEY)
}

export function startNewConversation(store: ConversationStore): ConversationStore {
  return { ...store, activeConversationId: null }
}

export function appendConversationTurn(
  store: ConversationStore,
  item: ConversationItem,
  newConversationId: string,
): ConversationStore {
  const active = store.conversations.find(
    (conversation) => conversation.id === store.activeConversationId,
  )
  if (!active) {
    const conversation: Conversation = {
      id: newConversationId,
      title: item.question,
      createdAt: item.createdAt,
      updatedAt: item.createdAt,
      turns: [item],
    }
    return {
      activeConversationId: conversation.id,
      conversations: [...store.conversations, conversation],
    }
  }

  return {
    ...store,
    conversations: store.conversations.map((conversation) => (
      conversation.id === active.id
        ? {
            ...conversation,
            updatedAt: item.createdAt,
            turns: [...conversation.turns, item].slice(-MAX_STORED_TURNS),
          }
        : conversation
    )),
  }
}

export function renameConversation(
  store: ConversationStore,
  conversationId: string,
  title: string,
): ConversationStore {
  const normalized = title.trim()
  if (!normalized || !store.conversations.some((conversation) => conversation.id === conversationId)) {
    return store
  }
  return {
    ...store,
    conversations: store.conversations.map((conversation) => (
      conversation.id === conversationId ? { ...conversation, title: normalized } : conversation
    )),
  }
}

export function selectConversation(
  store: ConversationStore,
  conversationId: string,
): ConversationStore {
  return store.conversations.some((conversation) => conversation.id === conversationId)
    ? { ...store, activeConversationId: conversationId }
    : store
}

export function deleteConversation(
  store: ConversationStore,
  conversationId: string,
): ConversationStore {
  if (!store.conversations.some((conversation) => conversation.id === conversationId)) return store
  const conversations = store.conversations.filter(
    (conversation) => conversation.id !== conversationId,
  )
  return {
    conversations,
    activeConversationId: store.activeConversationId === conversationId
      ? sortConversations(conversations)[0]?.id ?? null
      : store.activeConversationId,
  }
}

export function sortConversations(conversations: Conversation[]): Conversation[] {
  return [...conversations].sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))
}

function parseStoredValue(value: string | null): unknown {
  if (!value) return null
  try {
    return JSON.parse(value) as unknown
  } catch {
    return null
  }
}

function isConversationStore(value: unknown): value is ConversationStore {
  if (!value || typeof value !== 'object') return false
  const store = value as Partial<ConversationStore>
  if (!Array.isArray(store.conversations) || !store.conversations.every(isConversation)) return false
  return store.activeConversationId === null || (
    typeof store.activeConversationId === 'string' &&
    store.conversations.some((conversation) => conversation.id === store.activeConversationId)
  )
}

function isConversation(value: unknown): value is Conversation {
  if (!value || typeof value !== 'object') return false
  const conversation = value as Partial<Conversation>
  return (
    typeof conversation.id === 'string' &&
    typeof conversation.title === 'string' &&
    isTimestamp(conversation.createdAt) &&
    isTimestamp(conversation.updatedAt) &&
    Array.isArray(conversation.turns) &&
    conversation.turns.every(isConversationItem)
  )
}

function isConversationItem(value: unknown): value is ConversationItem {
  if (!value || typeof value !== 'object') return false
  const item = value as Partial<ConversationItem>
  return (
    typeof item.id === 'string' &&
    typeof item.question === 'string' &&
    isTimestamp(item.createdAt) &&
    !!item.result &&
    typeof item.result.answer === 'string' &&
    (item.result.mode === 'vector' || item.result.mode === 'hybrid') &&
    Array.isArray(item.result.sources) &&
    Array.isArray(item.result.graph_paths)
  )
}

function isTimestamp(value: unknown): value is string {
  return typeof value === 'string' && !Number.isNaN(Date.parse(value))
}
