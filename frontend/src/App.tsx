import { lazy, Suspense, useState } from 'react'

import DocumentsPage from './pages/DocumentsPage'
import QAPage from './pages/QAPage'

const GraphPage = lazy(() => import('./pages/GraphPage'))

type Page = 'documents' | 'graph' | 'qa'

const NAV_ITEMS: Array<{ id: Page; index: string; label: string }> = [
  { id: 'documents', index: '01', label: '文档' },
  { id: 'graph', index: '02', label: '知识图谱' },
  { id: 'qa', index: '03', label: '问答' },
]

export default function App() {
  const [page, setPage] = useState<Page>('documents')

  return (
    <div className="app-shell">
      <header className="app-header">
        <button className="brand" type="button" onClick={() => setPage('documents')}>
          <span>CR</span>
          <div>
            <strong>法规知识图谱 RAG</strong>
            <small>CAUSAL RULE RESEARCH SYSTEM</small>
          </div>
        </button>
        <nav aria-label="主导航">
          {NAV_ITEMS.map((item) => (
            <button
              className={page === item.id ? 'active' : ''}
              key={item.id}
              type="button"
              onClick={() => setPage(item.id)}
            >
              <small>{item.index}</small>
              {item.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="content-shell">
        {page === 'documents' && <DocumentsPage />}
        {page === 'graph' && (
          <Suspense fallback={<div className="panel page-loading">正在加载图谱组件…</div>}>
            <GraphPage />
          </Suspense>
        )}
        {page === 'qa' && <QAPage />}
      </main>

      <footer>
        <span>Knowledge Graph · Vector Retrieval · Evidence Grounding</span>
        <span>毕业论文实验系统 · V1</span>
      </footer>
    </div>
  )
}
