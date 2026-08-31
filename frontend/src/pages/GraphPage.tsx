import cytoscape, { type Core, type ElementDefinition } from 'cytoscape'
import { Maximize2, Network, Search, ZoomIn, ZoomOut } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { listDocuments, loadGraph } from '../api'
import type { DocumentSummary, GraphEdge, GraphNode, GraphResponse } from '../types'

type SelectedElement =
  | { kind: 'node'; value: GraphNode }
  | { kind: 'edge'; value: GraphEdge }
  | null

const ENTITY_COLORS: Record<string, string> = {
  LAW: '#2f7657',
  ARTICLE: '#4379a3',
  AGENCY: '#9b6b45',
  PERSON_ROLE: '#6a72a8',
  ORGANIZATION: '#40848a',
  LEGAL_CONCEPT: '#7463a3',
  ACTION: '#9a675d',
  RIGHT: '#4b8a68',
  OBLIGATION: '#a47b3c',
  PENALTY: '#a25151',
  OTHER: '#68766e',
}

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

  const visibleTypes = useMemo(
    () => [...new Set(visibleGraph.nodes.map((node) => node.type))].sort(),
    [visibleGraph.nodes],
  )

  useEffect(() => {
    if (!containerRef.current) return
    graphRef.current?.destroy()

    const elements: ElementDefinition[] = [
      ...visibleGraph.nodes.map((node) => ({
        group: 'nodes' as const,
        data: {
          id: node.id,
          label: node.label,
          type: node.type,
          color: ENTITY_COLORS[node.type] ?? ENTITY_COLORS.OTHER,
        },
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
      layout: { name: 'cose', animate: false, fit: true, padding: 54 },
      minZoom: 0.25,
      maxZoom: 3,
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'background-color': 'data(color)',
            color: '#24362c',
            'font-size': 11,
            'text-valign': 'bottom',
            'text-margin-y': 8,
            width: 34,
            height: 34,
            'border-width': 5,
            'border-color': '#e3ece6',
          },
        },
        {
          selector: 'edge',
          style: {
            label: 'data(label)',
            width: 1.4,
            'line-color': '#b7c4bc',
            'target-arrow-color': '#b7c4bc',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'font-size': 9,
            color: '#67756d',
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
    instance.on('tap', (event) => {
      if (event.target === instance) setSelected(null)
    })
    graphRef.current = instance

    return () => {
      instance.destroy()
      if (graphRef.current === instance) graphRef.current = null
    }
  }, [visibleGraph])

  function zoomBy(factor: number) {
    const instance = graphRef.current
    if (!instance) return
    instance.zoom(instance.zoom() * factor)
    instance.center()
  }

  return (
    <section className="graph-page">
      <div className="panel graph-toolbar">
        <label>
          <span>文档范围</span>
          <select value={documentId} onChange={(event) => setDocumentId(event.target.value)}>
            <option value="">全部已完成文档</option>
            {documents.map((document) => (
              <option value={document.id} key={document.id}>{document.filename}</option>
            ))}
          </select>
        </label>
        <label className="search-field">
          <Search size={16} />
          <input
            type="search"
            value={search}
            placeholder="搜索实体名称或类型"
            aria-label="搜索实体名称或类型"
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <div className="graph-toolbar-actions">
          <div className="graph-summary">
            <span><strong>{visibleGraph.nodes.length}</strong> 个实体</span>
            <span><strong>{visibleGraph.edges.length}</strong> 条关系</span>
          </div>
          <div className="graph-controls" aria-label="图谱缩放控制">
            <button type="button" aria-label="放大图谱" onClick={() => zoomBy(1.2)}><ZoomIn size={17} /></button>
            <button type="button" aria-label="缩小图谱" onClick={() => zoomBy(0.8)}><ZoomOut size={17} /></button>
            <button type="button" aria-label="复位图谱" onClick={() => graphRef.current?.fit(undefined, 54)}><Maximize2 size={17} /></button>
          </div>
        </div>
      </div>

      {error && <p className="error-banner">{error}</p>}
      {graph.truncated && <p className="notice-banner">实体超过 300 个，当前仅展示前 300 个。</p>}

      <div className="graph-workspace">
        <div className="panel graph-canvas-wrap">
          {visibleTypes.length > 0 && (
            <div className="graph-legend" aria-label="实体类型图例">
              {visibleTypes.map((type) => (
                <span key={type}><i style={{ background: ENTITY_COLORS[type] ?? ENTITY_COLORS.OTHER }} />{type}</span>
              ))}
            </div>
          )}
          <div className="graph-canvas" ref={containerRef} />
          {!loading && visibleGraph.nodes.length === 0 && (
            <div className="graph-empty"><Network size={32} /><span>没有可展示的实体关系</span></div>
          )}
          {loading && <div className="graph-empty">正在加载知识图谱…</div>}
        </div>

        <aside className="panel detail-panel">
          {!selected ? (
            <div className="detail-empty compact">
              <Network size={28} />
              <p>点击节点或关系查看类型和来源 Chunk。</p>
            </div>
          ) : selected.kind === 'node' ? (
            <>
              <span className="type-pill">{selected.value.type}</span>
              <h2>{selected.value.label}</h2>
              <p className="detail-label">来源分块</p>
              <ul className="source-id-list">
                {selected.value.source_chunk_ids.map((id) => <li key={id}>{id}</li>)}
              </ul>
            </>
          ) : (
            <>
              <span className="type-pill">RELATES_TO</span>
              <h2>{selected.value.predicate}</h2>
              <dl className="edge-detail">
                <dt>主体</dt><dd>{selected.value.source}</dd>
                <dt>客体</dt><dd>{selected.value.target}</dd>
                <dt>来源 Chunk</dt><dd>{selected.value.source_chunk_id}</dd>
              </dl>
            </>
          )}
        </aside>
      </div>
    </section>
  )
}
