import type { GraphEdge, GraphResponse } from './types'

interface GraphPosition {
  x: number
  y: number
}

interface GraphExportNode {
  id: string
  label: string
  type: string
  color: string
  source_chunk_ids: string[]
  position: GraphPosition
}

export interface GraphExportData {
  nodes: GraphExportNode[]
  edges: GraphEdge[]
}

export function truncateGraphLabel(label: string): string {
  const characters = Array.from(label)
  return characters.length > 10 ? `${characters.slice(0, 10).join('')}…` : label
}

export function buildGraphExport(
  graph: GraphResponse,
  positions: ReadonlyMap<string, GraphPosition>,
  colors: Readonly<Record<string, string>>,
  fallbackColor: string,
): GraphExportData {
  return {
    nodes: graph.nodes.map((node) => ({
      id: node.id,
      label: node.label,
      type: node.type,
      color: colors[node.type] ?? fallbackColor,
      source_chunk_ids: node.source_chunk_ids,
      position: positions.get(node.id)!,
    })),
    edges: graph.edges,
  }
}

function escapeXml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;')
}

export function serializeGraphMl(data: GraphExportData): string {
  const nodes = data.nodes.map((node) => `    <node id="${escapeXml(node.id)}">
      <data key="label">${escapeXml(node.label)}</data>
      <data key="type">${escapeXml(node.type)}</data>
      <data key="color">${escapeXml(node.color)}</data>
      <data key="source_chunk_ids">${escapeXml(JSON.stringify(node.source_chunk_ids))}</data>
      <data key="x">${node.position.x}</data>
      <data key="y">${node.position.y}</data>
    </node>`)
  const edges = data.edges.map((edge) => `    <edge id="${escapeXml(edge.id)}" source="${escapeXml(edge.source)}" target="${escapeXml(edge.target)}">
      <data key="predicate">${escapeXml(edge.predicate)}</data>
      <data key="source_chunk_id">${escapeXml(edge.source_chunk_id)}</data>
    </edge>`)

  return `<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="label" for="node" attr.name="label" attr.type="string"/>
  <key id="type" for="node" attr.name="type" attr.type="string"/>
  <key id="color" for="node" attr.name="color" attr.type="string"/>
  <key id="source_chunk_ids" for="node" attr.name="source_chunk_ids" attr.type="string"/>
  <key id="x" for="node" attr.name="x" attr.type="double"/>
  <key id="y" for="node" attr.name="y" attr.type="double"/>
  <key id="predicate" for="edge" attr.name="predicate" attr.type="string"/>
  <key id="source_chunk_id" for="edge" attr.name="source_chunk_id" attr.type="string"/>
  <graph id="knowledge-graph" edgedefault="directed">
${nodes.join('\n')}
${edges.join('\n')}
  </graph>
</graphml>
`
}
