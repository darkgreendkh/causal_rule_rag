import cytoscape, { type Core, type ElementDefinition } from 'cytoscape'
import { ChevronDown, Download, Network, Search, WandSparkles } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { listDocuments, loadGraph } from '../api'
import { buildGraphExport, serializeGraphMl, truncateGraphLabel } from '../graphExport'
import { groupSourceChunks } from '../sourceChunks'
import type { DocumentSummary, GraphEdge, GraphNode, GraphResponse } from '../types'

type SelectedElement =
  | { kind: 'node'; value: GraphNode }
  | { kind: 'edge'; value: GraphEdge }
  | null

const ENTITY_COLORS: Record<string, string> = {
  LAW: '#245c43',
  ARTICLE: '#356b91',
  AGENCY: '#815435',
  PERSON_ROLE: '#565f91',
  ORGANIZATION: '#287379',
  LEGAL_CONCEPT: '#655293',
  ACTION: '#865149',
  RIGHT: '#327550',
  OBLIGATION: '#8d6729',
  PENALTY: '#913f3f',
  OTHER: '#56645d',
}

const GRAPH_LAYOUT = {
  name: 'cose',
  fit: true,
  padding: 64,
  nodeOverlap: 20,
  idealEdgeLength: 110,
  componentSpacing: 100,
} as const

export default function GraphPage() {
  const containerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<Core | null>(null)
  const exportMenuRef = useRef<HTMLDetailsElement>(null)
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
    const closeExportMenu = (event: MouseEvent) => {
      const menu = exportMenuRef.current
      if (menu && event.target instanceof Node && !menu.contains(event.target)) {
        menu.open = false
      }
    }
    document.addEventListener('click', closeExportMenu)
    return () => document.removeEventListener('click', closeExportMenu)
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

  const sourceChunkGroups = useMemo(
    () => selected?.kind === 'node'
      ? groupSourceChunks(selected.value.source_chunk_ids, documents)
      : [],
    [documents, selected],
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
          displayLabel: truncateGraphLabel(node.label),
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
      layout: {
        ...GRAPH_LAYOUT,
        animate: false,
      },
      selectionType: 'single',
      minZoom: 0.1,
      maxZoom: 3,
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(displayLabel)',
            'background-color': 'data(color)',
            color: '#ffffff',
            'font-size': 10,
            'font-weight': 600,
            'text-halign': 'center',
            'text-valign': 'center',
            'text-justification': 'center',
            'text-wrap': 'wrap',
            'text-max-width': '52px',
            'text-overflow-wrap': 'anywhere',
            width: 68,
            height: 68,
            'border-width': 3,
            'border-color': '#ffffff',
            'overlay-opacity': 0,
          },
        },
        {
          selector: 'edge',
          style: {
            label: '',
            width: 1.5,
            'line-color': '#c7d0ca',
            'target-arrow-color': '#aebbb3',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'font-size': 9,
            color: '#526159',
            'text-background-color': '#ffffff',
            'text-background-opacity': 1,
            'text-background-padding': '4px',
            'text-background-shape': 'roundrectangle',
            'arrow-scale': 0.85,
            'overlay-opacity': 0,
          },
        },
        {
          selector: 'edge.relation-visible, edge.relation-hovered, edge:selected',
          style: {
            label: 'data(label)',
            width: 2.2,
            'line-color': '#718b7c',
            'target-arrow-color': '#718b7c',
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 5,
            'border-color': 'data(color)',
            'underlay-color': 'data(color)',
            'underlay-opacity': 0.16,
            'underlay-padding': 8,
            'underlay-shape': 'ellipse',
          },
        },
        {
          selector: 'edge:selected',
          style: {
            'line-color': '#d39f45',
            'target-arrow-color': '#d39f45',
          },
        },
        {
          selector: 'node.is-dimmed, edge.is-dimmed',
          style: { opacity: 0.14 },
        },
      ],
    })

    const clearFocus = () => {
      instance.elements().removeClass('is-dimmed relation-visible')
    }

    instance.on('tap', 'node', (event) => {
      clearFocus()
      const neighborhood = event.target.closedNeighborhood()
      instance.elements().difference(neighborhood).addClass('is-dimmed')
      neighborhood.edges().addClass('relation-visible')
      const value = visibleGraph.nodes.find((node) => node.id === event.target.id())
      if (value) setSelected({ kind: 'node', value })
    })
    instance.on('tap', 'edge', (event) => {
      clearFocus()
      const focus = event.target.connectedNodes().union(event.target)
      instance.elements().difference(focus).addClass('is-dimmed')
      event.target.addClass('relation-visible')
      const value = visibleGraph.edges.find((edge) => edge.id === event.target.id())
      if (value) setSelected({ kind: 'edge', value })
    })
    instance.on('mouseover', 'edge', (event) => event.target.addClass('relation-hovered'))
    instance.on('mouseout', 'edge', (event) => event.target.removeClass('relation-hovered'))
    instance.on('tap', (event) => {
      if (event.target === instance) {
        clearFocus()
        setSelected(null)
      }
    })
    graphRef.current = instance

    return () => {
      instance.destroy()
      if (graphRef.current === instance) graphRef.current = null
    }
  }, [visibleGraph])

  function arrangeGraph() {
    const instance = graphRef.current
    if (!instance || instance.nodes().empty()) return
    instance.layout({
      ...GRAPH_LAYOUT,
      animate: true,
      animationDuration: 500,
      randomize: true,
    }).run()
  }

  function exportTimestamp() {
    return new Date().toISOString().replaceAll('-', '').replaceAll(':', '').replace('T', '-').slice(0, 15)
  }

  function downloadBlob(blob: Blob, extension: string) {
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `knowledge-graph-${exportTimestamp()}.${extension}`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  function getExportData() {
    const positions = new Map(
      graphRef.current!.nodes().map((node) => [node.id(), node.position()] as const),
    )
    return buildGraphExport(visibleGraph, positions, ENTITY_COLORS, ENTITY_COLORS.OTHER)
  }

  function exportPng() {
    const blob = graphRef.current!.png({ output: 'blob', bg: '#ffffff', full: false, scale: 2 })
    downloadBlob(blob, 'png')
    exportMenuRef.current?.removeAttribute('open')
  }

  function exportJson() {
    const blob = new Blob([JSON.stringify(getExportData(), null, 2)], { type: 'application/json' })
    downloadBlob(blob, 'json')
    exportMenuRef.current?.removeAttribute('open')
  }

  function exportGraphMl() {
    const blob = new Blob([serializeGraphMl(getExportData())], { type: 'application/graphml+xml' })
    downloadBlob(blob, 'graphml')
    exportMenuRef.current?.removeAttribute('open')
  }

  const exportDisabled = loading || visibleGraph.nodes.length === 0

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
          <div className="graph-export-controls" aria-label="图谱导出控制">
            <details ref={exportMenuRef}>
              <summary
                aria-disabled={exportDisabled}
                onClick={(event) => exportDisabled && event.preventDefault()}
              >
                <Download size={15} /> 导出 <ChevronDown size={14} />
              </summary>
              <div className="graph-export-menu">
                <button type="button" onClick={exportPng}>PNG 图片</button>
                <button type="button" onClick={exportJson}>JSON 数据</button>
                <button type="button" onClick={exportGraphMl}>GraphML 图谱</button>
              </div>
            </details>
          </div>
          <div className="graph-controls" aria-label="图谱布局控制">
            <button type="button" disabled={exportDisabled} onClick={arrangeGraph}>
              <WandSparkles size={17} /> 一键整理
            </button>
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
              <p className="detail-label">来源依据</p>
              <ul className="source-id-list">
                {sourceChunkGroups.map((group) => (
                  <li key={group.documentId}>
                    {group.filename} · 分块 {group.chunkIndexes.join('、')}
                  </li>
                ))}
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
