# 论文初稿与后续补实验

题名：**基于规则约束与因果增强的智能审批关键技术研究**。

## 交付文件

- `基于规则约束与因果增强的智能审批关键技术研究（初稿）.docx`：可编辑Word，封面个人信息留空，中英文摘要、可更新目录、七章正文、顺序编码参考文献与致谢。
- 同名 `.md`：完整合并文稿；`chapters/` 保存分章源文，修改正文后应重新合成。
- `figures/`：10张方法图的DOT、SVG、PNG，7张由实际实验数据生成的第六章结果图，以及尚待标注实验的结果图占位。方法图保留DOT，结果图由 `generate_experiment_figures.py` 依据 `experiments/*.json` 重绘。
- `screenshots/`：实际运行系统的5张正文截图、贷款政策参数局部截图及工程验收记录。
- `policy-coverage.json`：36份政策、1481个单元及115个事项的逐项映射与能力清单。来源可追溯，但不表示全部条款已转成规则。
- `references.json`、`references-local.json`、`document-audit.json`：书目信息、核验说明、顺序编号映射和正文字数口径。
- `experiments/`：第一层实验的原始结果JSON与自动生成的汇总表，由 `backend/experiments/run_all.py` 写入。

当前知识快照为 `de0d04a9a1034b9e98b2da5ed4579c3d`：288条启用演示规则、233个动作、4503节点、7801边。102个来源单元被部分结构化；四类能力的事项数量为115/77/72/72。个人学术PDF与学长论文仍在原目录，不随本仓库公开提交。

## 实验现状

实验按金标准来源分两层，取舍与排期见 [实验计划](../experiment-plan.md)。

第一层（E04—E07、E09—E11）的金标准由语料结构或缺陷注入程序化确定，已经运行并填入正文表6-8至
表6-11、表6-13至表6-15与图6-4至图6-7、图6-9至图6-11。脚本在 `backend/experiments/`，
原始JSON与汇总表在 `docs/thesis/experiments/`。重跑方式（在 `backend/` 下）：

```powershell
$env:PYTHONUTF8='1'; $env:PYTHONPATH='.'; $env:HF_HOME='../.runtime/huggingface'
./.venv/Scripts/python.exe -m experiments.run_all
```

第二层（E01—E03、E08）需要独立双人标注，尚未开展，表6-5至表6-7、表6-12与图6-1至图6-3、
图6-8保持待标注标记。自动层数据不得用于支持回答正确性或规范解释质量的结论。

1. 按6.1完成抽取与问答标注，填写表6-5至表6-7、表6-12。表6-1、表6-2是资料与样本清点，不得改称效果评测。
2. 正式运行前复核表6-3，冻结代码、模型、知识版本与配置。接口配置名称不自动证明远程模型权重身份。
3. 第一层结果如与重跑不一致，应先核对构建快照与向量缓存版本，再修改结论，不保留旧数值。
4. 标注完成后重写6.7.1的假设汇总、6.8及摘要与总结中的效果性描述。没有改善或存在代价也应如实保留。
5. 重新生成图与Word、更新目录并检查分页。不要只修改合并稿而遗漏分章源文。

## 在当前Windows环境重新生成

```powershell
$env:PYTHONUTF8='1'
D:/anaconda/python.exe docs/thesis/generate_figures.py
D:/anaconda/python.exe docs/thesis/build_thesis.py --render
```

生成使用D盘Pandoc与本机Microsoft Word，公式保留OMML可编辑结构。Word导出的PDF和逐页PNG放在 `.runtime/thesis-qa/`，用于内部排版验收，不提交仓库。脚本通过独立的隐藏Word实例工作，不关闭用户正在编辑的文档。更换电脑时需配置脚本中Pandoc与Graphviz的路径，并安装python-docx、Pillow、pywin32、pypdfium2及Microsoft Word。

documents附带的artifact渲染器也已运行并逐页交叉检查，但该引擎存在OMML漏显、表列宽和分节页码兼容问题；最终版式以Microsoft Word实际导出和逐页检查为依据，未为适配辅助引擎删除公式或压平Word表格。
