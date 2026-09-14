# 论文方法—实现—页面—验证映射

本文按当前代码记录可追溯的实现，不把设计名词当作效果结论。验证用例是工程检查，未运行正式科研实验；真实全量 HTTP、浏览器验收由主集成任务执行。

## 三条主线与模块映射

| 方法环节 | 代码及实际定义 | 页面入口 | 主要验证用例 |
| --- | --- | --- | --- |
| 政策结构化与版本溯源 | `corpus._read_policy`、`_regulations`、`_units`；文件字节版本、独立规范和原文位置形成单元 ID | 文档页研究来源/原文定位 | `test_corpus.py::test_first_articles_of_multiple_regulations_do_not_collide`、`test_nonbreaking_space_indents_do_not_hide_entire_policy` |
| 研究文献摄取 | `corpus._read_references`；文本层提取、页码、文件哈希与解析器缓存 | 原文来源；未限事项的基础检索 | `test_every_policy_and_pdf_is_loaded_with_complete_coverage`、`test_pdf_text_cache_uses_source_hash_and_parser_version` |
| 全量事项及单元覆盖 | `policy_catalog.make_catalog`；115 事项，mapped/excluded，每项能力有来源、规则或动作支持 | 概览、文档覆盖与事项筛选 | `test_policy_catalog.py::test_all_six_policy_categories_have_executable_conditions`；`test_corpus.py` 全量覆盖检查 |
| 受限规则候选 | `candidate_extraction.extract_candidate_rules`；限定字段/动作、完整布尔表达式和原文 quote，候选不自动启用 | 文档页抽取候选、审核 | `test_candidate_extraction.py::test_candidate_is_never_active_and_requires_literal_source` |
| 规则版本核对 | `source_review_manifest.json` 与 `make_catalog`；初始固定 DSL 只适用于核对过的源字节版本 | 规则列表状态与错误说明 | `test_changed_source_does_not_reactivate_the_reviewed_old_threshold`、`test_source_review_manifest_covers_exactly_the_36_policy_versions` |
| 宏观/微观图构建 | `causal_graph.build_graph`；文件/事项/原文/角色/材料与条件/规则/动作/结果分层 | 图谱页三层视图、事项筛选 | `test_causal_graph.py::test_graph_preserves_each_and_condition_and_evidence`、`test_action_preconditions_and_not_have_directed_evidence_edges` |
| RPC | `rpc_score`；引用覆盖 coverage、结构 continuity、时空 temporal 三分量均值 | 边详情分量 | `test_rpc_reports_actual_scope_and_expression_components`、`test_rule_continuity_checks_linked_action_effect_fields` |
| SCS 与跨层关联 | `scs_score`；0.5×语义 + 0.3×来源支持 + 0.2×类型适配，不兼容为 0；只检查明确引用的单元—规则对 | REALIZES 边详情 | `test_scores_are_recomputable_and_reject_conflicting_scopes`、`test_missing_semantic_similarity_does_not_invent_a_perfect_match` |
| 时空/版本兼容 | `_scope_compatible`；地域、区间及同一规范版本比较；不同规范文号不视为同版本冲突 | 边兼容性、核查缺口 | `test_different_regulations_may_have_different_document_numbers`、`test_same_regulation_conflicting_versions_do_not_fuse` |
| 因果约束社区 | `assign_communities`；有效强依赖并查集合组→收缩图→Leiden modularity→局部 CPM 细分 | 社区/层级选择 | `test_must_link_groups_stay_together_after_community_assignment`、`test_hierarchy_keeps_must_links_and_reports_real_parent_membership` |
| 社区定位与有向候选 | `ResearchService.answer`、`path_candidates`；节点相似度聚合选社区，有向无重复节点路径，有界深度优先枚举 | 问答路径与图谱社区 | `test_paths_respect_direction_and_scoring_and_candidate_limit` |
| 路径评分与消融 | 语义均值、边 RPC 均值、邻接目标相似度 softmax 的归一化熵；完整配置 0.4/0.4/0.2 权重 | 完整方法及消融配置选择 | `test_path_score_ablations_change_only_the_intended_scoring_term` |
| 三值条件校验 | `rule_engine.validate_expression/evaluate`，缺字段、类型错误和未知作用域不能变成 satisfied | 事项事实表单、核查结果 | `test_rule_engine.py`；`test_each_reviewed_article_has_three_valued_source_example`、例外分支参数化测试 |
| 检索路径顺序校验 | `causal_validation.validate_path`；按路径动作推进状态，遗漏前缀未知，已知资格失败违规，未通过前缀后的节点延后验证 | 路径状态、首个阻断节点与缺口 | `test_causal_validation.py::test_path_replays_prepare_then_submit_without_mutating_inputs`、`test_missing_prefix_is_unknown_but_known_age_failure_remains_violated`、`test_unknown_external_action_stops_effects_and_marks_suffix_unverified` |
| 状态重放 | `workflow.check_workflow`；按历史及拟执行动作顺序检查，满足后才施加效果 | 历史步骤、拟执行步骤和模拟状态 | `test_workflow.py::test_replay_applies_effects_in_order_without_mutating_inputs`、`test_history_is_replayed_and_never_repaired` |
| 准备与提交阶段 | `action_id` 约束动作，`purpose=condition_check` 兼容空步骤事实核查 | 准备材料→提交申请 | `test_condition_check_rule_allows_preparation_but_still_guards_submission`、`test_real_injury_preparation_and_minimal_material_repair` |
| 外部确认与政策参数隔离 | `_Context` 过滤请求中的 policy 字段；external 效果必须等于原始外部事实 | 只读政策字段、外部事实和下一步预览 | `test_policy_facts_cannot_be_overridden`、`test_external_approval_requires_original_confirmed_fact` |
| 最小编辑修复 | `repair_workflow`；插入/删除/替换单位代价优先队列搜索，历史与不可变事实保持；默认 5000 状态 | 修复建议与修改后核查 | `test_repair_matches_exhaustive_minimum_for_all_short_sequences`、`test_repair_distinguishes_unknown_unreachable_and_truncation` |
| 下一步与结果预览 | `next_steps` 逐动作检查，满足才有 preview_state | 下一步候选、确认加入步骤 | `test_repair_inserts_required_predecessor_and_preview_is_nonmutating` |
| 六类真实流程 | `policy_catalog` 中养老、医疗、失业、工伤、生育、公积金动作目录 | 事项选择及流程模拟 | `test_six_real_services_check_and_repair_from_source_examples`：每类正常/违规/缺信息/补回前置动作 |
| 版本持久化与失效 | `research_store.ResearchRepository`、`ResearchService`；快照、Neo4j 投影、独立配置版本头 | 构建、审核、来源移除 | `test_build_persists_separate_profiles_and_counts`、`test_rebuilding_changed_sources_invalidates_other_profiles`、`integration/test_research_store.py` |
| 有序证据生成 | `ResearchService.answer` 保留完整必要引文、来源预算与缺口；生成不替代程序结果 | 问答来源、规则核查、有序路径 | `test_causal_answer_checks_all_and_conditions_and_records_run`、`test_without_evidence_chain_preserves_rule_checks_and_missing_fact_guidance` |

## 对照与消融的精确口径

| 入口 | 来源与检索 | 不应作出的解释 |
| --- | --- | --- |
| uploaded/vector | 上传 TXT/MD 的 Chunk，Neo4j Top 5 | 不能与不同解析语料的研究方法直接作为同源对照 |
| uploaded/hybrid | 相同 Chunk 的实体一跳扩展，最多增加 3 个 | 不执行研究规则或动作状态重放 |
| research/vector | 同一研究快照的政策单元及未限事项时的 PDF 页，向量 Top 8 | 相似文本不等于政策适用或资格满足 |
| research/hybrid | 前 4 个来源种子经宏观普通邻接扩展，补齐至 8 | 扩展忽略因果方向及规则约束 |
| research/causal | 政策图社区→有向候选→规则核查→必要原文证据→回答 | 一条有向路径不等于全部条件成立或完整流程已办理 |

`research_profiles.py` 提供完整配置以及移除 RPC、SCS、宏观层、微观层、社区硬约束、语义项、熵项、检索规则过滤、有序证据链的九个配置。它们分别构建且有独立 build_id；“移除检索规则过滤”不关闭流程 API 的确定性校验。

默认 RPC/SCS 阈值均为 0.7，强依赖阈值 0.85，随机种子 42，社区最大 3 层、Top 3 社区、最多 6 跳、100 候选、8 条来源证据、5 条返回路径。候选枚举后在当前候选内排序；不能宣称全图全局最优路径。熵项是邻接选择分散度的工程量，不是生成模型的不确定性估计。

## 不能夸大的实现边界

1. 宏观事实主要由政策结构、目录和字段生成。初始规则不是对全部正文自动抽取后得到的专家金标准；模型候选也不会自动成为可执行规则。
2. RPC 的 coverage 是可定位引文占声明引文的比例，不是全部必要法律条件已完整识别的比例；continuity 是表达式、字段、动作及依赖的结构检查。
3. SCS 没有搜索任意宏观—微观配对，没有执行通用跨分块实体消歧。同一动作的宏/微视图是身份链接，scs=1 表示同一个目录动作，不是模型判断得到的完美语义相似度。
4. PDF 文献页没有进入 `build_graph`，没有文献—政策的跨层规则链。其用途是背景检索，不支持行政决定。
5. 结构化贷款条件检查不提供最终可贷金额；配套标准和信用、房产记录、退休边界须来自对应政策参数或外部事实。外部事实本身目前没有联网认证。
6. 检索路径校验与完整办理历史不能混同：未来步骤尚未执行不应被解释为申请资格违规。`validate_path` 已实现路径顺序重放与缺前缀的 unknown 语义，13 个独立工程回归通过；最终 HTTP 与浏览器验收仍由主集成任务执行。
7. 当前只报告单元测试、集成测试、清点数量和研发运行记录。没有正式实验结果、有效性提升数值、用户研究或显著性检验。
