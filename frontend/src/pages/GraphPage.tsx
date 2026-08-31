import cytoscape, { type Core, type ElementDefinition } from 'cytoscape'
import { useEffect, useMemo, useRef, useState } from 'react'

import { listDocuments, loadGraph } from '../api'
import type { DocumentSummary, GraphEdge, GraphNode, GraphResponse } from '../types'

type SelectedElement =
  | { kind: 'node'; value: GraphNode }
  | { kind: 'edge'; value: GraphEdge }
  | null

export default function GraphPage() {
  const containerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<Core | null>(null)
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [documentId, setDocumentId] = useState('')
  const [search, setSearch] = useState('')
  const [graph, setGraph] = useState<GraphResponse>({ nodes: [], edges: [], truncated: false })
  const [selected, setSelected] = useState<SelectedElement>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    void listDocuments()
      .then((items) => setDocuments(items.filter((item) => item.status === 'COMPLETED')))
      .catch(() => setDocuments([]))
  }, [])

  useEffect(() => {
    setLoading(true)
    setError('')
    setSelected(null)
    void loadGraph(documentId || null)
      .then(setGraph)
      .catch((requestError: unknown) => {
        setGraph({ nodes: [], edges: [], truncated: false })
        setError(requestError instanceof Error ? requestError.message : '图谱加载失败')
      })
      .finally(() => setLoading(false))
  }, [documentId])

  const visibleGraph = useMemo(() => {
    const keyword = search.trim().toLocaleLowerCase()
    if (!keyword) return graph
    const nodes = graph.nodes.filter(
      (node) =>
        node.label.toLocaleLowerCase().includes(keyword) ||
        node.type.toLocaleLowerCase().includes(keyword),
    )
    const nodeIds = new Set(nodes.map((node) => node.id))
    return {
      ...graph,
      nodes,
      edges: graph.edges.filter(
        (edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target),
      ),
    }
  }, [graph, search])

  useEffect(() => {
    if (!containerRef.current) return
    graphRef.current?.destroy()

    const elements: ElementDefinition[] = [
      ...visibleGraph.nodes.map((node) => ({
        group: 'nodes' as const,
        data: { id: node.id, label: node.label, type: node.type },
      })),
      ...visibleGraph.edges.map((edge) => ({
        group: 'edges' as const,
        data: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.predicate,
        },
      })),
    ]

    const instance = cytoscape({
      container: containerRef.current,
      elements,
      layout: { name: 'cose', animate: false, fit: true, padding: 36 },
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'background-color': '#2f7657',
            color: '#173226',
            'font-size': 11,
            'text-valign': 'bottom',
            'text-margin-y': 8,
            width: 34,
            height: 34,
            'border-width': 5,
            'border-color': '#d9eadf',
          },
        },
        {
          selector: 'edge',
          style: {
            label: 'data(label)',
            width: 1.5,
            'line-color': '#afbeb5',
            'target-arrow-color': '#afbeb5',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'font-size': 9,
            color: '#66736d',
            'text-background-color': '#f8faf8',
            'text-background-opacity': 1,
            'text-background-padding': '3px',
          },
        },
        {
          selector: ':selected',
          style: { 'border-color': '#d39f45', 'line-color': '#d39f45' },
        },
      ],
    })

    instance.on('tap', 'node', (event) => {
      const value = visibleGraph.nodes.find((node) => node.id === event.target.id())
      if (value) setSelected({ kind: 'node', value })
    })
    instance.on('tap', 'edge', (event) => {
      const value = visibleGraph.edges.find((edge) => edge.id === event.target.id())
      if (value) setSelected({ kind: 'edge', value })
    })
    graphRef.current = instance

    return () => {
      instance.destroy()
      if (graphRef.current === instance) graphRef.current = null
    }
  }, [visibleGraph])

  return (
    <section className="graph-page">
      <div className="panel graph-toolbar">
        <div>
          <p className="section-kicker">KNOWLEDGE GRAPH</p>
          <h2>法规实体关系</h2>
        </div>
        <label>
          文档范围
          <select value={documentId} onChange={(event) => setDocumentId(event.target.value)}>
            <option value="">全部已完成文档</option>
            {documents.map((document) => (
              <option value={document.id} key={document.id}>
                {document.filename}
              </option>
            ))}
          </select>
        </label>
        <label>
          搜索节点
          <input
            type="search"
            value={search}
            placeholder="实体名称或类型"
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
      </div>

      {error && <p className="error-banner">{error}</p>}
      {graph.truncated && <p className="notice-banner">节点超过 300 个，当前仅展示前 300 个。</p>}

      <div className="graph-layout">
        <div className="panel graph-canvas-wrap">
          <div className="graph-stats">
            <span>{visibleGraph.nodes.length} 个实体</span>
            <span>{visibleGraph.edges.length} 条关系</span>
          </div>
          <div className="graph-canvas" ref={containerRef} />
          {!loading && visibleGraph.nodes.length === 0 && (
            <div className="graph-empty">没有可展示的实体关系</div>
          )}
          {loading && <div className="graph-empty">正在加载知识图谱…</div>}
        </div>

        <aside className="panel detail-panel">
          <p className="section-kicker">DETAIL</p>
          {!selected ? (
            <p className="muted">点击节点或关系查看类型和来源 Chunk。</p>
          ) : selected.kind === 'node' ? (
            <>
              <span className="type-pill">{selected.value.type}</span>
              <h3>{selected.value.label}</h3>
              <p className="muted">来源分块</p>
              <ul className="source-id-list">
                {selected.value.source_chunk_ids.map((id) => (
                  <li key={id}>{id}</li>
                ))}
              </ul>
            </>
          ) : (
            <>
              <span className="type-pill">RELATES_TO</span>
              <h3>{selected.value.predicate}</h3>
              <dl className="edge-detail">
                <dt>主体</dt>
                <dd>{selected.value.source}</dd>
                <dt>客体</dt>
                <dd>{selected.value.target}</dd>
                <dt>来源 Chunk</dt>
                <dd>{selected.value.source_chunk_id}</dd>
              </dl>
            </>
          )}
        </aside>
      </div>
    </section>
  )
}
