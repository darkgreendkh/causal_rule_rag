import {
  Files,
  LayoutDashboard,
  MessageCircleQuestion,
  Network,
  Scale,
  type LucideIcon,
} from 'lucide-react'
import { lazy, Suspense, useState } from 'react'

import DocumentsPage from './pages/DocumentsPage'
import OverviewPage from './pages/OverviewPage'
import QAPage from './pages/QAPage'

const GraphPage = lazy(() => import('./pages/GraphPage'))

export type Page = 'overview' | 'documents' | 'graph' | 'qa'

const NAV_ITEMS: Array<{ id: Page; label: string; icon: LucideIcon }> = [
  { id: 'overview', label: '概览', icon: LayoutDashboard },
  { id: 'documents', label: '文档管理', icon: Files },
  { id: 'graph', label: '知识图谱', icon: Network },
  { id: 'qa', label: '法规问答', icon: MessageCircleQuestion },
]

export default function App() {
  const [page, setPage] = useState<Page>('overview')

  function navigate(nextPage: Page) {
    setPage(nextPage)
    window.scrollTo({ top: 0 })
  }

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <Brand onClick={() => navigate('overview')} />
        <nav aria-label="主导航">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            return (
              <button
                className={page === item.id ? 'active' : ''}
                key={item.id}
                type="button"
                onClick={() => navigate(item.id)}
              >
                <Icon aria-hidden="true" size={19} strokeWidth={1.8} />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>
        <div className="sidebar-note">
          <Scale aria-hidden="true" size={17} />
          <span>毕业论文实验系统 · V1</span>
        </div>
      </aside>

      <div className="app-workspace">
        <header className="mobile-header">
          <Brand onClick={() => navigate('overview')} compact />
        </header>
        <main className="content-shell">
          {page === 'overview' && <OverviewPage onNavigate={navigate} />}
          {page === 'documents' && <DocumentsPage />}
          {page === 'graph' && (
            <Suspense fallback={<div className="panel page-loading">正在加载图谱组件…</div>}>
              <GraphPage />
            </Suspense>
          )}
          {page === 'qa' && <QAPage />}
        </main>
      </div>
    </div>
  )
}

function Brand({ onClick, compact = false }: { onClick: () => void; compact?: boolean }) {
  return (
    <button className="brand" type="button" onClick={onClick} aria-label="返回概览">
      <span>CR</span>
      <div>
        <strong>法规知识图谱 RAG</strong>
        {!compact && <small>CAUSAL RULE RESEARCH SYSTEM</small>}
      </div>
    </button>
  )
}
