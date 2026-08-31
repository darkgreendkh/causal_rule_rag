const sections = ['文档', '知识图谱', '问答']

export default function App() {
  return (
    <main className="shell">
      <header>
        <p className="eyebrow">CAUSAL RULE RAG</p>
        <h1>法规知识图谱 RAG</h1>
        <p>上传法规文档，检查结构化分块，并通过向量与图谱检索获得可追溯回答。</p>
      </header>
      <nav aria-label="主导航">
        {sections.map((section) => (
          <button key={section} type="button">
            {section}
          </button>
        ))}
      </nav>
      <section className="empty-state">
        <span>一期基础工程</span>
        <h2>服务已准备好接入 RAG 流程</h2>
      </section>
    </main>
  )
}
