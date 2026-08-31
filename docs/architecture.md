# 系统架构

本文只描述当前已实现的架构。功能发生变化时，应同步更新本文、`features.md` 和
`decisions.md`。

## 总体组成

| 层次 | 技术 | 职责 |
| --- | --- | --- |
| 前端 | React、TypeScript、Vite、Cytoscape.js | 文档管理、Chunk 查看、知识图谱展示和问答交互 |
| 后端 | FastAPI、Python 3.12 | API、文档摄取、分块、图谱抽取、检索和回答生成 |
| 文件存储 | `data/uploads/` | 保存上传的 TXT/Markdown 原文件 |
| Embedding | 本地 BGE-M3 | 批量生成归一化的 1024 维向量 |
| 数据库 | Neo4j 5.26 Community | 保存文档元数据、Chunk、实体关系和向量索引 |
| 大模型 | OpenAI 兼容 Chat Completions 接口 | 抽取三元组和生成带引用的回答 |

当前没有单独部署向量数据库：Neo4j 的 `chunk_embedding` 向量索引承担向量召回，
Neo4j 图模型承担一跳关系扩展。

## 核心数据流

### 文档摄取

```text
TXT / Markdown
      ↓
格式、UTF-8、空内容和 SHA-256 判重校验
      ↓
结构化分块（标题 / 法规条款 / 段落 / 表格）
      ├──→ BGE-M3 Embedding ──→ Neo4j Chunk 向量索引
      └──→ LLM JSON 三元组 ──→ Neo4j Entity / RELATES_TO
```

后端接收文件后返回 `202`，再通过 FastAPI `BackgroundTasks` 执行处理。文档状态依次为：

```text
PENDING → PARSING → EMBEDDING → EXTRACTING_GRAPH → COMPLETED
                                                       ↘ FAILED
```

### 问答

```text
问题 → BGE-M3 查询向量 → Neo4j 向量 Top 5
                              ├── vector：直接组成上下文
                              └── hybrid：实体一跳扩展，最多补充 3 个 Chunk
                                           ↓
                               去重后的最多 8 个 Chunk
                                           ↓
                              LLM 回答 + [S1] 来源标记
```

当前检索链路没有 reranker、关键词检索、多轮会话或流式输出。

## 后端模块

| 模块 | 职责 |
| --- | --- |
| `app/main.py` | 创建应用、注入服务、CORS、生命周期和健康检查 |
| `app/api/` | 文档、图谱和问答 HTTP API |
| `app/chunking.py` | 按标题、条款、段落和表格分块 |
| `app/ingestion.py` | 上传校验、处理状态编排、失败清理和删除原文件 |
| `app/embedding.py` | 延迟加载 BGE-M3 并生成归一化向量 |
| `app/extraction.py` | 约束 LLM 输出并校验三元组 JSON |
| `app/qa.py` | 纯向量/混合检索编排和回答提示词 |
| `app/database.py` | Neo4j 约束、索引、数据写入、查询和清理 |
| `app/models.py` | API、状态、实体、来源和图谱数据模型 |
| `app/config.py` | 环境变量和默认配置 |

应用配置由 `create_app` 注入；自动化测试显式传入测试配置，不读取开发者本地的 LLM
密钥与模型设置。

## 前后端通信

前端通过 `frontend/src/api.ts` 使用 HTTP JSON API 调用 FastAPI。开发环境默认是：

```text
Browser :5173 → FastAPI :8000 → Neo4j Bolt :7687
                              → OpenAI 兼容 LLM API
                              → 本地 BGE-M3
```

文件上传使用 `multipart/form-data`；其余写接口使用 JSON。前端每 3 秒轮询文档列表以
更新处理状态。CORS 默认只允许 `http://localhost:5173`。

## Neo4j 数据模型

```text
(Document)-[:HAS_CHUNK]->(Chunk)-[:MENTIONS]->(Entity)
(Entity)-[:RELATES_TO {predicate, source_chunk_id}]->(Entity)
```

- `Document.id`、`Document.sha256`、`Chunk.id`、`Entity.key` 有唯一约束。
- `Chunk.embedding` 使用 1024 维 cosine 向量索引。
- `Entity.key` 由实体类型和规范化名称组成，用于跨 Chunk 合并实体。
- `source_chunk_id` 用于从关系回溯原文，也用于按文档清理派生关系。
- 数据库边界将 Neo4j `DateTime` 转为 Python `datetime`；Neo4j 未保存的可空 Chunk
  属性在 API 模型中恢复为 `None`。

## 目录结构

```text
causal_rule_rag/
├── backend/
│   ├── app/                 FastAPI 业务代码
│   ├── tests/               单元、API 和 Neo4j 集成测试
│   ├── pyproject.toml       Python 依赖与工具配置
│   └── uv.lock              Python 锁文件
├── frontend/
│   ├── src/pages/           文档、图谱、问答页面
│   ├── src/api.ts           后端 API 客户端
│   ├── src/types.ts         前端接口类型
│   └── package.json         前端依赖与命令
├── data/uploads/            上传原文件，内容不提交到 Git
├── docs/                    架构、功能和技术决策
├── examples/                演示法规文档
├── docker-compose.yml       Neo4j 本地运行配置
└── README.md                安装、启动和验证入口
```
