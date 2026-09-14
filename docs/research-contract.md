# 研究模块共享接口（实施契约）

## 数据结构

均为JSON可序列化dict。稳定id由内容/来源生成，中文label供界面显示。

- Evidence: `{unit_id, source_path, title, article, quote}`，quote必须在对应unit.text中。
- Unit: `{id, document_id, source_path, title, article, text, category, region, valid_from, valid_to, validity_known}`。文件可含多部规范，unit id不可仅按条号生成。
- Document: `{id, source_path, filename, sha256, category, region, source_url, published_at, unit_count}`。
- Field: `{id,label,type,role,unit?,options?,mutable?}`；type为boolean/number/date/enum/text/set，role为applicant/policy/external。options为字符串数组。
- Matter: `{id,name,category,description,fields,policy_parameters,rule_ids,action_ids,goals,capabilities,gaps,source_unit_ids}`。goals为`[{id,label,condition}]`。capabilities为`{retrievable,checkable,simulatable,repairable}`。gaps为中文字符串数组。
- Rule: `{id,matter_id,label,condition,action_id,scope,evidence,status,review_source,validation_errors}`。scope=`{region,valid_from,valid_to,validity_known}`，region字符串（全国/湖北/武汉），status=candidate/active/rejected/disabled。action_id可null。
- Action: `{id,matter_id,label,preconditions,effects,kind,evidence}`；kind=user/external，effects为字段到新值的映射。external动作必须由外部已确认事实支持，不能模拟制造审批结果。
- Coverage: `{unit_id,matter_ids,disposition,reason}`，disposition=mapped/excluded，每一unit必须有记录，排除必须说明原因。
- Corpus: `{documents,units,matters,rules,actions,coverage,references}`，各字段都是list。references条目保留PDF名称、page、text，不产生active审批规则。

## 表达式

- 常量：`{"value":18}`；字段：`{"field":"age"}`。
- 比较：`{"op":"gte","left":{"field":"age"},"right":{"value":18}}`。
- 支持eq/ne/gt/gte/lt/lte/in/contains。
- 布尔：`{"all":[expression,...]}`、`{"any":[...]}`、`{"not":expression}`。
- 前置动作：`{"completed":"action_id"}`。
- 数值：`{"op":"add|sub|mul|div|min|max","args":[value_expression,...]}`。
- 条件常量`{"value":true}`只用于真实无额外前置条件的动作，不能替代资料未知。

## rules agent导出（app/rule_engine.py、app/workflow.py）

- `validate_expression(expression: dict, field_ids: set[str]) -> list[str]`
- `evaluate(expression: dict, facts: dict, completed: list[str] | None = None) -> dict`：`{status,missing_fields,reasons}`，status=satisfied/violated/unknown。
- `check_workflow(corpus:dict, request:dict) -> dict`
- `repair_workflow(corpus:dict, request:dict, max_states:int=5000) -> dict`
- `next_steps(corpus:dict, request:dict) -> dict`
- request: `{matter_id,region,as_of,facts,steps,completed_steps,goal,profile?}`，steps为拟执行动作id数组，completed_steps为不可撤销历史动作id数组，缺省均[]。facts的policy角色字段不得覆盖matter.policy_parameters。
- check返回`{status,checks,first_error,missing_fields,knowledge_gaps,state,completed_steps,goal_satisfied}`；checks含rule_id,label,status,evidence；first_error为null或`{index,action_id,kind,message}`。
- repair返回`{status,edits,steps,cost,checked,explored_states,truncated}`，status=repaired/already_valid/unknown/unreachable/truncated。仅修复拟执行序列，绝不重写历史或不可变事实。
- next返回`{status,candidates,state}`；candidate含action_id,label,status,missing_fields,evidence,preview_state。前端确认后才应用到本地模拟。

## corpus agent导出（app/corpus.py、app/policy_catalog.py，可加research_data/*.json）

- `build_corpus(data_dir: Path) -> dict`，只读取原始文件；调用方负责保存结果。
- 用初始核对规则包提供真实可执行条件，全部办理相关条款映射事项，资料不足保留gaps，不能只做两个事项。
- 库内可执行规则status=active时review_source明确`implementation_source_review`；模型新抽取一律candidate，不宣称专家审核。
- 36份政策、8份文献均进入结果。PDF支持通过pdfplumber/pypdf读取，缺依赖时报告明确错误，不静默跳过。

## root提供给前端的HTTP

- GET `/api/research/status`: `{status,stage,error,build_id,profile,counts}`。
- POST `/api/research/build`: `{profile?:string}` -> 202同status。
- GET `/api/research/summary`: `{counts,matters,documents,profiles,build_id,gaps}`。
- GET `/api/research/matters` -> Matter[]；GET `/api/research/matters/{id}` -> Matter。
- GET `/api/research/rules?matter_id=&status=` -> Rule[]。
- POST `/api/research/rules/review`: `{rule_ids,action}`；action=activate/reject/disable；返回`{results,build_id}`，result含id,status,error。
- GET `/api/research/coverage` -> Coverage[]。
- POST `/api/research/workflow/check|repair|next` -> 上述workflow结果。
- GET `/api/research/graph?layer=fused|macro|micro&matter_id=&community_id=&limit=300` -> `{nodes,edges,truncated,communities,build_id}`。节点兼容旧GraphNode并加layer/community_id；边兼容旧GraphEdge并加type/layer/rpc/scs/evidence/rule_ids。
- POST `/api/qa`新增mode=causal，可选matter_id,region,as_of,facts,profile；保留原history。
- QAResponse新增可选`causal_paths,rule_checks,communities,knowledge_gaps,run_id`，旧字段answer/mode/sources/graph_paths不变。
- causal_paths项`{id,node_ids,edge_ids,labels,score,semantic_score,rpc,entropy,evidence,rule_ids}`。
- `/api/research/summary`的profiles为`[{id,label,description}]`，前端只需用于研究配置选择。

## 所有权

agents不编辑彼此文件；共享models/main/api/qa由root编辑。前端只编辑frontend目录。不提交其他人的改动。测试使用backend/.venv/Scripts/python.exe。
