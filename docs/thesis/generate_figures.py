"""Generate editable Graphviz sources, SVG and print-resolution PNG figures."""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'figures'
FIGURES = {
    'fig1-1-technical-route': ('研究技术路线', '''
      source [label="政策原文与研究文献\n法源、地域、版本、条款 / PDF 页码"];
      inventory [label="全量覆盖与事项建模\n条件、动作、证据及知识缺口"];
      dual [label="规则约束的双层图谱\n宏观语义层 + 微观约束层\nRPC / SCS 筛选"];
      retrieval [label="约束社区与多跳检索\n强约束收缩 → Leiden → 有向路径"];
      application [label="证据问答与流程纠错\n三态检查 / 最低编辑成本修复 / 下一步预览"];
      protocol [label="实验设计与待验证假设\n对比、消融、参数与统计分析\n本次科研结果留空",style="rounded,dashed"];
      source -> inventory -> dual -> retrieval -> application -> protocol;
    '''),
    'fig3-1-dual-graph': ('双层图谱与证据连接', '''
      graph [splines=line, overlap=true];
      macro_frame [shape=box,style="",label="宏观语义层",labelloc=t,pos="122,220!",width=3.8,height=4.31,fontsize=16,color="#7c8b97"];
      micro_frame [shape=box,style="",label="微观约束层",labelloc=t,pos="505,162!",width=3.7,height=5.92,fontsize=16,color="#7c8b97"];
      subgraph cluster_macro { label="宏观语义层"; labeljust=l; color="#7c8b97"; margin=16;
        doc [label="法规版本",pos="190,320!"]; article [label="政策条款",pos="190,210!"];
        matter [label="办理事项",pos="50,320!"]; role [label="参与角色",pos="50,210!"];
        material [label="材料 / 字段",pos="50,100!"];
        operation [label="业务操作",pos="190,100!"];
        doc -> article [label="CONTAINS"];
        matter -> article [label="依据条款"];
        matter -> role [label="INVOLVES"]; role -> material [label="PROVIDES"];
        matter -> operation [label="HANDLES"];
      }
      subgraph cluster_micro { label="微观约束层"; labeljust=l; color="#7c8b97"; margin=16;
        c1 [label="必要条件 A",pos="440,320!"]; c2 [label="必要条件 B",pos="570,320!"];
        rule [label="AND 规则",pos="505,210!"];
        action [label="动作及前置条件",pos="505,100!"];
        state [label="允许的模拟状态\n外部结果须事实确认",pos="505,-10!"];
        c1 -> rule [label="REQUIRES"]; c2 -> rule [label="REQUIRES"];
        rule -> action [label="REQUIRES"]; action -> state [label="PRODUCES"];
      }
      link_rule [shape=plain,style="",label="REALIZES\n引用 + SCS",pos="315,210!",fontsize=11,fontcolor="#345d7e"];
      link_action [shape=plain,style="",label="REALIZES\n同一操作",pos="315,100!",fontsize=11,fontcolor="#345d7e"];
      article -> link_rule [arrowhead=none,color="#345d7e"]; link_rule -> rule [color="#345d7e"];
      operation -> link_action [arrowhead=none,color="#345d7e"]; link_action -> action [color="#345d7e"];
    '''),
    'fig3-2-rpc': ('RPC 规则路径一致性指标', '''
      input [label="候选规则或动作\n受限表达式 + 独立原文引用"];
      evidence [label="证据覆盖 Cₑ\n逐字可定位引用 / 所有引用"];
      continuity [label="条件衔接 Cₗ\n字段、动作引用与效果定义闭合"];
      temporal [label="时间与顺序 Cₜ\n适用域交集 + 必需前置无环"];
      aggregate [label="RPC = (Cₑ + Cₗ + Cₜ) / 3"];
      filter [label="阈值筛选与分量留存\n默认 0.7；强约束默认 0.85"];
      note [label="结构筛选指标\n不证明政策解释或抽取内容真实",style="rounded,dashed"];
      input -> evidence; input -> continuity; input -> temporal;
      evidence -> aggregate; continuity -> aggregate; temporal -> aggregate;
      aggregate -> filter -> note;
    '''),
    'fig3-3-scs': ('SCS 跨层连接筛选', '''
      pair [label="来自已定位原文引用的\n条款—微观规则候选对"];
      conflict [label="地域、日期区间\n及同规范版本有冲突？",shape=diamond];
      reject [label="拒绝融合\n不受消融开关放行"];
      parts [label="计算三个评分分量"];
      semantic [label="BGE 稠密余弦 s\n截断至 [0, 1]"];
      support [label="逐字引用覆盖率 e"];
      type [label="条款 → 规则\n类型兼容 t = 1"];
      score [label="SCS = 0.5s + 0.3e + 0.2t"];
      retain [label="保留达到阈值的 REALIZES 边\n记录两端 ID、全部引用、评分分量"];
      pair -> conflict; conflict -> reject [label="有冲突"];
      conflict -> parts [label="无冲突"]; parts -> semantic; parts -> support; parts -> type;
      semantic -> score; support -> score; type -> score; score -> retain;
    '''),
    'fig4-1-community': ('约束保持的社区构建', '''
      original [label="原始有向知识图\n语义权重与证据属性"];
      group [label="识别 active、高 RPC、无冲突关系\n并查集合并强约束组"];
      contract [label="收缩成无向加权商图\n聚合组间权重与组内自环权重"];
      leiden [label="Leiden 粗层划分\n模块度目标；固定随机种子 42"];
      refine [label="诱导子图递归细分\nCPM 目标；至多三级"];
      expand [label="展开原节点归属\n保存父子社区、成员及不可拆分标记"];
      query [label="原始有向边继续用于检索和规则检查"];
      original -> group -> contract -> leiden -> refine -> expand;
      original -> query [style=dashed,label="方向不被收缩图替代"];
      expand -> query;
    '''),
    'fig4-2-directed-search': ('有向候选路径检索与评分', '''
      question [label="问题、事项、地域与办理日期\n已知事实及完成记录"];
      embed [label="问题向量与节点相关性"];
      coarse [label="粗粒度社区筛选\n默认保留三个社区"];
      search [label="原始有向图候选搜索\n最多六跳、100 个候选；禁止节点循环"];
      rule [label="沿路径检查完整规则并重放动作\n首次未知或违反后停止推进"];
      rank [label="评分 = 0.4 × 平均语义相关性\n+ 0.4 × 平均 RPC\n+ 0.2 × (1 − 平均归一化分支熵)"];
      evidence [label="补齐完整必要证据\n证据预算不足则报告缺口"];
      answer [label="有序路径、分量与可定位引用\n未知不等于审批通过"];
      question -> embed -> coarse -> search -> rank -> rule -> evidence -> answer;
    '''),
    'fig4-3-evidence': ('必要证据组织与生成约束', '''
      path [label="候选有向路径"];
      owners [label="关联规则与动作的完整表达式"];
      ands [label="AND 必要条件集合\nOR / NOT 保持原逻辑"];
      refs [label="来源存在且引用逐字匹配\n去重后最多八个条款单元"];
      gaps [label="缺事实 / 缺规则 / 外部待确认\n来源缺失 / 引用不符 / 超预算",style="rounded,dashed"];
      prompt [label="生成输入\n原文编号 + 证据完整的检查与路径 + 缺口"];
      result [label="回答 [S1]…\n路径、规则检查与缺口同时展示"];
      path -> owners -> ands -> refs -> prompt -> result;
      ands -> gaps; refs -> gaps; gaps -> prompt [label="仅缺口提示"];
    '''),
    'fig5-1-architecture': ('系统实现架构', '''
      graph [compound=true];
      subgraph cluster_browser { label="浏览器：React + TypeScript + Vite"; labeljust=l; color="#7c8b97";
        pages [label="概览 / 文档管理 / 知识图谱 / 法规问答"];
        forms [label="动态事实表单、步骤序列\n原文审阅、图谱与模拟状态"];
        history [label="浏览器会话存储\n兼容既有问答记录"];
        pages -> forms; pages -> history;
      }
      subgraph cluster_backend { label="FastAPI / Python 3.12"; labeljust=l; color="#7c8b97";
        api [label="问答、图谱、构建、规则与流程 API"];
        corpus [label="全量原文解析与事项目录\n候选抽取、结构校验及审核"];
        kg [label="双层图谱、RPC / SCS\nLeiden 社区与路径检索"];
        workflow [label="受限 JSON 规则引擎\n重放、修复和下一步计算"];
        service [label="配置版本、证据组织与运行日志"];
        api -> corpus; api -> kg; api -> workflow; corpus -> kg;
        kg -> service; workflow -> service;
      }
      neo4j [label="Neo4j\n基础图 + 增强节点/关系 + 有效版本头"];
      disk [label="D 盘本地文件\n原始资料 / PDF 与向量缓存\n版本快照 / 运行日志"];
      model [label="BGE-M3 本地向量模型\n已配置的大模型接口"];
      forms -> api [label="HTTP JSON",ltail=cluster_browser,lhead=cluster_backend];
      service -> neo4j; corpus -> disk; service -> disk; kg -> model;
      corpus -> model [style=dashed,label="候选抽取"];
      service -> model [style=dashed,label="回答生成"];
    '''),
    'fig5-2-repair-search': ('带序列位置的状态空间修复', '''
      input [label="不可撤销历史 + 待执行序列 + 目标"];
      replay [label="逐步重放并定位首个问题"];
      valid [label="已经满足？",shape=diamond];
      unchanged [label="返回原计划与零成本"];
      base [label="事项前置与历史可重放？",shape=diamond];
      search [label="优先队列 Dijkstra 搜索\n状态：序列位置、事实、已完成动作集合"];
      edit [label="保留 0 / 插入 1 / 删除 1 / 替换 1\n动作须通过同一规则引擎"];
      goal [label="出队状态：序列末尾\n且目标满足？",shape=diamond];
      check [label="完整重放复验通过？",shape=diamond];
      output [label="编辑项、总成本、修复序列及验证结果"];
      stopped [label="信息不足 / 无解 / 搜索截断\n最多 5000 个状态",style="rounded,dashed"];
      input -> replay -> valid; valid -> unchanged [label="是"]; valid -> base [label="否"];
      base -> search [label="是"]; base -> stopped [label="否"];
      search -> goal; goal -> edit [label="否"]; edit -> search [label="候选入队"];
      goal -> check [label="是"]; check -> edit [label="否"];
      search -> stopped [label="边界/知识限制"]; check -> output [label="是"];
    '''),
    'fig5-3-interaction': ('检查、修复与模拟推进闭环', '''
      facts [label="填写已知事实\n未知保持为空；政策参数只读"];
      steps [label="区分已完成历史与拟执行步骤"];
      check [label="后端检查 / 修复 / 下一步计算"];
      preview [label="展示原因、证据与新状态预览"];
      apply [label="用户点击应用到当前模拟",shape=diamond];
      state [label="更新本地模拟计划或状态"];
      note [label="不连接真实政务执行端\n不生成外部机关审批结果",style="rounded,dashed"];
      facts -> steps -> check -> preview -> apply;
      apply -> state [label="确认"]; apply -> facts [label="继续修改"];
      state -> check; state -> note;
    '''),
    'experiment-results-placeholder': ('科研实验图占位', '''
      blank [label="此处插入正式实验结果图\n\n当前未开展科研效果评测\n完成实验后替换图像并更新图题和分析",width=6.3,height=2.4,style="rounded,dashed"];
    '''),
}


def main():
    dot = shutil.which('dot')
    if not dot:
        raise RuntimeError('Graphviz dot is required')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, (title, body) in FIGURES.items():
        source = ('digraph G {\n'
                  'graph [rankdir=TB, bgcolor="white", fontname="Microsoft YaHei", fontsize=16, pad=0.18, nodesep=0.35, ranksep=0.42, splines=polyline, dpi=220];\n'
                  'node [shape=box, style="rounded,filled", fillcolor="#f5f8fa", color="#43576a", '
                  'fontname="Microsoft YaHei", fontsize=14, margin="0.16,0.10", penwidth=1.1];\n'
                  'edge [fontname="Microsoft YaHei", fontsize=11, color="#526575", arrowsize=0.65];\n'
                  + body + '\n}\n')
        # Python multiline strings use literal escaped newline sequences inside DOT labels.
        import re
        source = re.sub(r'"([^"\\]*(?:\\.[^"\\]*)*)"',
                        lambda m: '"' + m.group(1).replace('\n', '\\n') + '"', source)
        source = '\n'.join(line.rstrip() for line in source.splitlines()) + '\n'
        path = OUTPUT / (name + '.dot')
        path.write_text(source, encoding='utf-8')
        for format in ('svg', 'png'):
            layout = ['-Kneato', '-n2'] if name == 'fig3-1-dual-graph' else []
            subprocess.run([dot, *layout, '-T' + format, str(path), '-o', str(OUTPUT / (name + '.' + format))], check=True)
        print(name, title)


if __name__ == '__main__':
    main()
