# 法规知识图谱 RAG

研究生毕业论文一期项目：上传 TXT/Markdown 法规文档，完成结构化分块、向量索引、
知识图谱抽取，并通过纯向量或图谱增强检索生成带原文证据的回答。

## 项目文档

- [系统架构](docs/architecture.md)
- [功能与模块说明](docs/features.md)
- [重要技术决策](docs/decisions.md)

功能新增、修改或删除时，必须同步检查并更新以上三份文档，使其始终反映当前代码；
`decisions.md` 只记录会持续影响项目的重要选择，不记录普通实现细节。

## 一期能力

- 上传 UTF-8 编码的 `.txt`、`.md` 文档，按标题、法规条款、段落和表格分块。
- 使用本地 `BAAI/bge-m3` 生成 1024 维 embedding。
- 在 Neo4j 中同时保存 Document、Chunk、Entity、三元组关系和向量索引。
- 使用 OpenAI 兼容接口抽取法律实体关系和生成最终回答。
- 支持纯向量 Top 5 与“向量 Top 5 + 图谱一跳扩展 Top 3”两种检索模式。
- React 研究工作台展示概览、文档进度、原始分块、实体关系、答案来源和图谱路径。
- 支持基于最近三轮历史的问题改写与多轮追问，最近会话保存在浏览器本地。

## 数据流

```text
TXT / Markdown
      ↓
结构化分块（标题 / 第 X 条 / 表格）
      ↓
BGE-M3 embedding ──────────────→ Neo4j Chunk 向量索引
      ↓
LLM JSON 三元组抽取 ──────────→ Neo4j Entity / RELATES_TO
                                      ↓
用户问题 → 向量召回 → 一跳图扩展 → 带 [S1] 来源的回答
```

图数据模型：

```text
(Document)-[:HAS_CHUNK]->(Chunk)-[:MENTIONS]->(Entity)
(Entity)-[:RELATES_TO {predicate, source_chunk_id}]->(Entity)
```

## 环境要求

- macOS/Linux
- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 22 与 pnpm 10
- Docker Desktop（用于运行 Neo4j 5.26 Community）
- 一个支持 Chat Completions 的 OpenAI 兼容大模型接口

## 启动

### 1. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`：

```dotenv
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=change-me

LLM_BASE_URL=https://你的服务地址/v1
LLM_API_KEY=你的密钥
LLM_MODEL=你的模型名称

EMBEDDING_MODEL=BAAI/bge-m3
```

LLM 三项配置必须同时填写，否则文档会在图谱抽取阶段明确标记为失败。密钥只保存在
本地 `.env`，该文件已被 Git 忽略。

### 2. 启动 Neo4j

确认 Docker Desktop 已运行：

```bash
docker compose up -d
docker compose ps
```

Neo4j Browser：<http://localhost:7474>，用户名为 `neo4j`，密码来自 `.env`。

### 3. 启动后端

```bash
cd backend
uv sync --group dev
uv run uvicorn app.main:app --reload --port 8000
```

首次进行文档处理或问答时会下载 BGE-M3 模型并缓存到本机，因此第一次运行会较慢。

- 健康检查：<http://localhost:8000/api/health>
- OpenAPI 文档：<http://localhost:8000/docs>

### 4. 启动前端

新开一个终端：

```bash
cd frontend
pnpm install
pnpm dev
```

访问 <http://localhost:5173>。

## 使用流程

1. 在“文档”页上传 `examples/legal_sample.md`。
2. 等待状态依次经过等待处理、解析、向量化、图谱抽取并变为“已完成”。
3. 在“文档管理”页选择已完成文档，检查法规条款和 Markdown 表格是否保持完整。
4. 在“知识图谱”页筛选文档，点击节点或关系查看来源 Chunk。
5. 在“问答”页分别使用纯向量与混合检索提问，对比来源与图谱扩展路径。
6. 继续追问包含指代或省略的问题，检查每轮回答使用的独立证据。

处理失败时，系统保留原文件和错误信息，并清理已经生成的 Chunk 与关系。删除文档会
同时删除原文件、向量、来源关系和不再被引用的孤立实体。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/health` | Neo4j、embedding 模型和 LLM 配置状态 |
| `POST` | `/api/documents` | 上传单个 TXT/Markdown，返回 `202` |
| `GET` | `/api/documents` | 文档列表和处理进度 |
| `GET` | `/api/documents/{id}/chunks` | 文档分块 |
| `DELETE` | `/api/documents/{id}` | 删除文档及关联数据 |
| `GET` | `/api/graph?document_id=&limit=300` | 实体节点和关系边 |
| `POST` | `/api/qa` | `{question, mode, history?}`，历史最多三轮 |

问答响应包含 `answer`、`sources` 和 `graph_paths`。每个 Source 会标明文档、Chunk、
相似度及 `vector/graph` 召回渠道。

## 验证

后端单元/API 测试与静态检查：

```bash
cd backend
uv run --group dev pytest -q
uv run --group dev ruff check .
```

默认测试会跳过需要真实 Neo4j 的集成用例。请使用专用测试实例运行：

```bash
cd backend
NEO4J_TEST_URI=bolt://localhost:7687 \
NEO4J_TEST_USER=neo4j \
NEO4J_TEST_PASSWORD=change-me \
uv run --group dev pytest tests/integration -q
```

集成测试会创建和删除自己的测试文档；不要把它指向包含重要数据的 Neo4j 实例。

前端检查：

```bash
cd frontend
pnpm lint
pnpm build
```

## 项目结构

```text
backend/                 FastAPI、分块、embedding、图谱、检索和测试
frontend/                React 文档页、知识图谱页和问答页
data/uploads/            本地上传文件（Git 忽略）
examples/legal_sample.md 端到端演示法规
docker-compose.yml       Neo4j Community
```

## 一期边界

当前版本是论文创新实验的基础对照系统，不包含 PDF/Word/OCR、用户登录、多租户、
服务端会话持久化、reranker、关键词检索、流式输出、图谱人工编辑和生产部署。多轮
记录只保存在当前浏览器。后续创新点应以独立实验变量逐项接入，保留 `vector` 模式
作为消融对照。
