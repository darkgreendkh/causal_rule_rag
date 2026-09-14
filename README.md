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
- 支持基于最近三轮历史的问题改写与多轮追问，可在浏览器本地管理多个会话。

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

- macOS/Linux；本机 Windows 启动方式见下文
- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 22 与 pnpm 10
- Docker Desktop（用于运行 Neo4j 5.26 Community）
- 一个支持 Chat Completions 的 OpenAI 兼容大模型接口

## 启动

### 本机 Windows 环境

本机已在 D 盘安装依赖，并复用 `D:/backend/neo4j-community-5.26.8`、
`D:/backend/Java/jdk-21` 和 `D:/tools/nodejs`。填写根目录 `.env` 后，
在项目目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-windows.ps1
```

脚本在后台启动 Neo4j、后端和前端，访问 <http://localhost:5173>。
已有监听端口会跳过启动。日志位于 `.runtime/logs/`；运行环境和数据位置如下：

- Python 3.12：`D:/uv/python`；后端虚拟环境：`backend/.venv/`。
- pnpm：`.runtime/tools/`；前端依赖：`frontend/node_modules/`。
- BGE-M3 模型缓存：`.runtime/huggingface/`。
- 本项目独立 Neo4j 数据：`.runtime/neo4j/data/`，配置：`.runtime/neo4j/conf/`。
- 上传原文件：`data/uploads/`；Neo4j 用户名 `neo4j`，初始密码 `change-me`。

`.runtime/` 已被 Git 忽略，但包含数据库和模型，不应作为普通临时目录删除。
此启动脚本对应本机已有安装路径。修改 `.env` 后需重启后端。
如需在终端前台运行单个服务，可使用 `-Service neo4j`、`-Service backend`
或 `-Service frontend`，然后通过 `Ctrl+C` 停止该服务。

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

## 规则与因果增强研究系统

概览页可构建 `data/guojia_shebao`、`data/wuhan_shebao` 中的全部政策和
`data/research_papers` 中带文本层的 PDF。当前资料包含 36 份政策与 8 篇文献，形成
115 个事项目录、288 条经实现者原文核对的演示规则、233 个动作。文献只用于辅助检索。
全量事项映射不意味着所有条款已转成可执行规则；各事项分别展示检索、条件检查、
流程模拟和修复能力及资料缺口，见 [覆盖说明](docs/data-coverage.md)。

1. 概览页选择研究配置并构建；不同配置保存独立快照，构建状态与错误实时可见。
2. 文档页查看原文、法规单元、适用日期及规则；自动抽取只产生候选，审阅后才能启用。
3. 图谱页切换宏观、微观和融合图，按事项、社区筛选，查看方向、RPC/SCS 与来源。
4. 问答页选择研究资料库和 `vector`、`hybrid` 或 `causal` 模式，输入事项、地域及业务日期。
5. 在页内流程面板填写已知事实与步骤，检查首错、预览修复和下一步，再应用到当前模拟。

API 增量入口位于 `/api/research`，接口字段见
[研究接口约定](docs/research-contract.md) 和运行中的 `/docs`。旧上传资料库与浏览器会话继续可用。
研究库移除文档保留原文件；旧上传接口的删除行为仍会删除其上传副本。

新增内容持久化在 Neo4j 的 ResearchNode / RESEARCH_LINK 与 `.runtime/research/`：
快照含条款、向量、规则、图谱和社区，JSONL 日志记录配置、构建和运行，审阅记录绑定规则与原文指纹。
原文修改、规则停用或重建会使旧关联结果失效。政策原文由 `.gitattributes` 保留字节与换行，避免跨平台检出改变审核哈希。
用户提供的学术 PDF、参考学位论文、密钥与缓存保留本地，不提交 Git。

Windows 当前使用 D 盘的 Python、Node、Neo4j、Java 与 BGE-M3 缓存，运行 `./start-windows.ps1`。
`backend/uv.lock` 固定依赖；Windows AMD64 使用 PyTorch 2.9.1 + CUDA 12.6，已验证本机 RTX 4060 可用。
研究库首次构建需要计算向量，后续重建复用内容缓存。

隔离命名空间的研究存储测试（不删除原知识库）：

```powershell
cd backend
$env:RUN_RESEARCH_NEO4J_TESTS='1'
./.venv/Scripts/python.exe -m pytest tests/integration/test_research_store.py -q
```

实现架构、边界与论文方法映射见 [架构](docs/architecture.md)、[功能](docs/features.md)、
[技术决策](docs/decisions.md) 和 [方法映射](docs/method-implementation-mapping.md)。
论文源文、Word 与可编辑图源位于 `docs/thesis/`。

## 实验

实验按金标准来源分两层，取舍、样本量与排期见 [实验计划](docs/experiment-plan.md)。
第一层（E04—E07、E09—E11）的金标准由语料结构或缺陷注入程序化确定，已实现在
`backend/experiments/` 并完成运行；第二层（E01—E03、E08）需要独立人工标注，尚未开展。

第一层离线运行，只读 `data/` 与 `.runtime/research/embeddings.json` 的向量缓存，
不连 Neo4j、不调用生成模型、不写入正式知识库：

```powershell
cd backend
$env:PYTHONUTF8='1'; $env:PYTHONPATH='.'; $env:HF_HOME='../.runtime/huggingface'
./.venv/Scripts/python.exe -m experiments.run_all
```

结果 JSON 与汇总表写入 [docs/thesis/experiments/](docs/thesis/experiments/)；
第六章结果图由 `docs/thesis/generate_experiment_figures.py` 按同一批 JSON 重绘。
