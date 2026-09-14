# 摘要

社会保险与住房公积金办理涉及多来源政策、地域差异、时效条件和跨条款流程依赖。通用检索增强生成系统能够为问题寻找相关文本，但文本相关性不足以说明审批条件是否满足，普通图谱中的连接关系也不能直接证明步骤顺序合理。当申请材料不完整、政策参数缺失或外部结果尚未确认时，仅依靠自然语言生成容易混淆办理建议与确定性判断。针对这些问题，本文围绕规则约束、方向依赖和证据组织，研究智能审批辅助系统的关键技术。

首先，提出规则约束的双层知识表示方法，在宏观层组织事项、规范、条款、角色、材料和操作，在微观层表达条件、动作、结果状态与例外。通过受限JSON表达式和三态逻辑保留条件结构，区分申请人事实、政策参数及外部核验结果，并使用原文引用与版本标识实现追溯。在此基础上，定义RPC与SCS筛选指标，分别度量证据覆盖、表达式衔接、时间顺序相容以及跨层连接的语义和来源支撑。

其次，设计约束保持的社区与多跳检索方法。对经过审核、高置信且无冲突的强依赖组进行收缩，在加权图上调用Leiden算法形成社区，再展开原始节点归属。有向检索保留原图的前置与产出关系，结合语义相关性、RPC和归一化分支熵排序候选路径，并补齐AND条件所需的证据。本文所称因果增强主要指有原文支撑的规范性方向依赖，不估计现实中的干预效应，也不把评分解释为已校准的因果概率。

最后，构建证据问答、流程检查和编辑修复的交互闭环。系统逐步重放办理计划，定位首个不满足或未知的步骤；在保持不可变事实与既有历史的条件下，使用包含序列位置的状态空间搜索寻找声明成本下的修复方案，并对结果完整重放验证。原型基于Windows环境实现前后端联动，保留基础检索模式、知识版本和研究配置，按条款公开事项支持范围与资料缺口。

本文以36份政策和8篇研究文献组织研究资料，建立后续对比、消融、参数与误差分析的实验协议。本初稿不预填科研实验结果，方法效果及相应统计结论留待按照实验协议完成验证。

**关键词：** 智能审批；检索增强生成；知识图谱；规则约束；流程修复

# Abstract

Social insurance and housing provident fund services involve policies from multiple sources, jurisdictional and temporal conditions, and procedural dependencies distributed across provisions. Retrieval-augmented generation can locate relevant text, but relevance alone does not establish eligibility or procedural validity. This thesis studies rule-constrained and causally enhanced methods for an evidence-based approval assistance system.

A dual-layer knowledge representation organizes matters, regulations, provisions, roles, materials, and operations at the macro level, while representing conditions, actions, states, and exceptions at the micro level. A restricted JSON expression language and three-valued evaluation distinguish satisfied, violated, and unknown conditions. Applicant facts, policy parameters, and externally confirmed results have separate semantics. Two implementation-specific indicators, RPC and SCS, support structural consistency screening and cross-layer alignment while retaining locatable source evidence.

A constraint-preserving retrieval method contracts reviewed, high-confidence dependency groups before applying Leiden community detection and subsequently restores original node membership. Directed candidate paths are ranked using semantic relevance, RPC, and normalized branching entropy. Necessary evidence is completed for conjunctive conditions. Causal enhancement here refers to source-supported normative dependencies and state transitions; it does not identify real-world intervention effects or calibrated causal probabilities.

The prototype combines evidence-grounded question answering with ordered workflow replay, bounded sequence repair, and next-action previews. Repair preserves immutable facts and completed history and minimizes the declared edit cost within the specified action space and search boundary. The Windows implementation retains baseline retrieval modes, versioned knowledge snapshots, configuration records, and explicit capability gaps. The study organizes 36 policy documents and eight research publications and specifies subsequent comparative, ablation, parameter, and error-analysis experiments. Research results and empirical conclusions are intentionally left unfilled in this draft.

**Keywords:** approval assistance; retrieval-augmented generation; knowledge graph; rule constraints; workflow repair
