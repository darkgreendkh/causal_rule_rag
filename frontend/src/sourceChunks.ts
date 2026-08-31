interface SourceDocument {
  id: string
  filename: string
}

export interface SourceChunkGroup {
  documentId: string
  filename: string
  chunkIndexes: number[]
}

export function groupSourceChunks(
  sourceChunkIds: string[],
  documents: SourceDocument[],
): SourceChunkGroup[] {
  const filenames = new Map(documents.map((document) => [document.id, document.filename]))
  const groups = new Map<string, SourceChunkGroup>()

  for (const sourceChunkId of sourceChunkIds) {
    const separator = sourceChunkId.lastIndexOf(':')
    const documentId = sourceChunkId.slice(0, separator)
    const chunkIndex = Number(sourceChunkId.slice(separator + 1))
    const group = groups.get(documentId) ?? {
      documentId,
      filename: filenames.get(documentId) ?? documentId,
      chunkIndexes: [],
    }
    group.chunkIndexes.push(chunkIndex)
    groups.set(documentId, group)
  }

  return [...groups.values()].map((group) => ({
    ...group,
    chunkIndexes: group.chunkIndexes.sort((left, right) => left - right),
  }))
}
