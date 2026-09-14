# 系统架构

本文描述上传资料库与研究资料库两条实际实现链路。下文原有文档摄取、Chunk 索引和实体一跳检索属于上传资料库；研究资料库的来源、规则、图和状态重放见后半部分。功能变化时同步更新本文、`features.md` 和 `decisions.md`。

## 总体组成

| 层次 | 技术 | 职责 |
| --- | --- | --- |
| 前端 | React、TypeScript、Vite、Cytoscape.js、Lucide | 概览、文档管理、Chunk 查看、知识图谱展示和多轮问答交互 |
| 后端 | FastAPI、Python 3.12 | API、文档摄取、分块、图谱抽取、检索和回答生成 |
| 文件存储 | `data/uploads/` | 保存上传的 TXT/Markdown 原文件 |
| Embedding | 本地 BGE-M3 | 批量生成归一化的 1024 维向量 |
| 数据库 | Neo4j 5.26 Community | 保存文档元数据、Chunk、实体关系和向量索引 |
| 大模型 | OpenAI 兼容 Chat Completions 接口 | 抽取三元组和生成带引用的回答 |

当前没有单独部署向量数据库。上传资料库使用 Neo4j 的 `chunk_embedding` 向量索引和实体一跳扩展；研究资料库的查询在版本快照的向量上计算点积，并读取其独立图结构。

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

有对话历史时，前端携带最近三轮问题和回答，后端先将当前追问改写为独立检索问题，
再进入上述检索链路。历史只帮助理解问题，本轮证据仍是回答的唯一事实依据。当前检索
链路没有 reranker、关键词检索或流式输出。

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
更新处理状态。问答页在浏览器 localStorage 保存多个本地会话，每个会话最多 20 轮
完整结果；请求时只发送当前会话最近三轮问答文本。CORS 默认只允许
`http://localhost:5173`。

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

## 研究资料库的领域边界

| 术语 | 含义与边界 |
| --- | --- |
| 来源文件 / 独立规范 / 原文单元 | 一个文件可以合载多部规范；单元包含条款、章节或发布说明，不能将单元总数称为办理规则数 |
| 事项 | 按业务对象与办理行为识别的目录项；有来源不代表已完整编码审批条件 |
| 初始核对规则 | 对指定来源字节版本核对的受限表达式；`implementation_source_review` 不代表专家审核或现行政策认证 |
| 候选规则 | 尚未启用的模型输出，或原来源变化后待重新核对的固定规则 |
| 外部事实 | 用户提供的已知机构核验、鉴定或审批结果；系统没有接入真实行政审批系统验证这些陈述 |
| 模拟状态 / 办理结果 | 模拟状态用于重放动作和预览；只有已确认的外部事实才能登记外部结果 |
| 四项能力 | 可检索、可核查、可模拟、可修复的结构化支持标记；具体请求仍须满足日期、地域、字段和规则状态 |

## 研究构建链路

```text
36 份政策 TXT → corpus.py → 文件 / 独立规范 / 1481 原文单元
                                 ↓
                  policy_catalog.py + 来源 SHA-256 核对清单
                                 ↓
                  事项 / 字段 / 规则 / 动作 / 目标 / 覆盖清单

8 篇 PDF → pdfplumber 原文本层 → 357 个带页码背景记录
                                 ↓
                     BGE-M3 文本向量缓存

政策单元 + 规则 + 动作 → 双层图 / RPC / SCS → 约束社区
                                 ↓
              JSON 版本快照 + Neo4j 独立研究图投影
```

`corpus.py` 只读取原始资料，另存可重建的 PDF 文本缓存。文件 SHA-256、规范序号和名称、单元位置与原文共同形成单元标识。固定规则必须匹配 `research_data/source_review_manifest.json` 中已核对的来源版本；变更来源生成带错误说明的候选，受影响事项执行能力暂停。

宏观层含文件、条款、事项、角色、材料/概念和动作视图；微观层含条件、规则、动作和结果状态。AND 条件拆为必要条件节点，OR 与 NOT 保留整体语义。有向边表达 `REQUIRES`、`PRECEDES`、`PRODUCES` 和 `EXCEPTS`。跨层关联限于明确来源引用与同一动作身份，当前没有对任意跨分块实体自动作语义合并。

RPC 是来源引用覆盖、结构连续性和时空兼容三个工程分量的均值；SCS 是语义、来源支持和类型适配的加权值。它们不是经过实验校准的正确率或政策效力概率。强依赖先收缩为不可拆组，再使用 Leiden 划分社区；随后在保留组的前提下生成层级。候选检索有跳数、数量与证据预算上限。

PDF 记录保留在快照及向量检索中，当前没有作为政策节点加入 `build_graph`，也不生成审批条件。选定事项时检索限于该事项政策来源，PDF 背景页不参与该事项的审批路径。

## 研究运行与模块

| 模块 | 职责 |
| --- | --- |
| `app/corpus.py` / `app/policy_catalog.py` | 原文解析、版本核对、目录和初始规则包 |
| `app/candidate_extraction.py` | 有界候选抽取、DSL 与逐字引文校验，不自动启用 |
| `app/rule_engine.py` | 类型受限表达式的 satisfied / violated / unknown 计算 |
| `app/workflow.py` | 历史重放、动作效果、目标检查、最小编辑修复、下一步预览 |
| `app/causal_validation.py` | 按检索路径顺序重放真实动作；缺少已执行前缀为 unknown，已知条件失败仍为 violated |
| `app/causal_graph.py` | 双层图、RPC/SCS、强依赖收缩、社区和有向路径评分 |
| `app/research_profiles.py` | 完整方法及九个独立开关配置，默认值未经过正式实验调优 |
| `app/research.py` | 构建、审核、移除来源、三模式检索、生成与运行日志 |
| `app/research_store.py` | 快照文件、Neo4j 研究图投影与配置版本头 |
| `app/api/research.py` | 研究 API；`app/api/qa.py` 按 dataset/mode 分流 |

上传图继续使用 `Document/Chunk/Entity/RELATES_TO`。研究图使用 `KnowledgeSnapshot`、`ResearchHead`、`ResearchNode` 和 `RESEARCH_LINK`，按 namespace、profile 和 build_id 隔离。完整 JSON 快照是重放依据，Neo4j 保存可检查的节点和边投影；新投影完成后才切换版本头。来源变化或审核变化使相关旧配置失效，磁盘旧快照保留供核查。

研究向量缓存键包含模型名和文本；同一语料不同研究配置复用向量，但有各自 build_id。运行日志记录配置、输入、结果、耗时及 build_id，属于工程审计记录。它们不能直接当作正式科研实验结果。

## 流程核查边界

申请事实、不可被请求覆盖的政策参数、外部事实具有不同角色。只有声明可变的申请字段能被用户动作修改；外部动作的每个效果必须已在请求原始事实中存在且同值。未知参数、缺材料事实、缺外部确认和超出已知时空范围返回 unknown。

资格规则绑定实际受限动作；`purpose=condition_check` 同时支持空步骤的事实核查。准备动作不提前执行提交阶段资格条件。修复只对拟执行序列做单位代价的插入、删除、替换，保留历史、政策参数与不可变事实；达到状态预算返回 truncated，不宣称全局无解。下一步只返回可预览结果，不持久化真实办理状态。

完整方法的路径检索和流程重放是不同入口：一条检索路径不能证明全部 AND 条件成立。接口与浏览器最终验收由集成任务执行，本文不以静态实现代替真实 HTTP 或前端验收。
