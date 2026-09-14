"""Run every annotation-free experiment and render the tables used in chapter 6.

Usage (from backend/):
    PYTHONPATH=. HF_HOME=../.runtime/huggingface .venv/Scripts/python.exe -m experiments.run_all
"""

import json
import platform
import subprocess
import sys
from datetime import UTC, datetime

from experiments import (
    e04_graph,
    e05_community,
    e06_retrieval,
    e09_repair,
    e10_next,
    e11_update,
)
from experiments.harness import RESULT_DIR, ROOT, reference_report, snapshot, write_result

EXPERIMENTS = {
    "e04-graph": e04_graph.run,
    "e05-community": e05_community.run,
    "e06-retrieval": e06_retrieval.run,
    "e09-repair": e09_repair.run,
    "e10-next": e10_next.run,
    "e11-update": e11_update.run,
}


def _commit() -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _flatten(values: dict) -> dict:
    result = {}
    for key, value in values.items():
        if isinstance(value, dict):
            result.update({f"{key}.{sub}": item for sub, item in value.items()})
        else:
            result[key] = value
    return result


def _table(rows: dict[str, dict], first: str) -> list[str]:
    rows = {name: _flatten(values) for name, values in rows.items()}
    columns: list[str] = []
    for values in rows.values():
        for key in values:
            if key not in columns:
                columns.append(key)
    lines = [
        "| " + " | ".join([first, *columns]) + " |",
        "| " + " | ".join(["---"] * (len(columns) + 1)) + " |",
    ]
    for name, values in rows.items():
        cells = [str(values.get(key, "")) for key in columns]
        lines.append("| " + " | ".join([name, *cells]) + " |")
    lines.append("")
    return lines


def render(results: dict, meta: dict) -> str:
    lines = [
        "# 自动实验结果（无需人工标注部分）",
        "",
        (
            f"运行时间：{meta['run_at']}；代码版本：{meta['commit']}；"
            f"节点/边：{meta['nodes']}/{meta['edges']}。"
        ),
        "",
        "本文件由 `backend/experiments/run_all.py` 生成，请勿手工编辑。指标口径、",
        "银标准来源与有效性威胁见 `docs/experiment-plan.md` 与论文 6.1、6.7。",
        "",
        "## E04 双层图谱构建消融（结构指标）",
        "",
    ]
    lines += _table(results["e04-graph"]["profiles"], "配置")
    binding = results["e04-graph"]["threshold_binding"]
    lines += [
        (
            "阈值生效检查："
            f"{binding['causal_edges']}条方向边中有{binding['causal_rpc_below_threshold']}条低于"
            f"RPC阈值{binding['rpc_threshold']}，RPC取值集合为{binding['distinct_rpc_values']}；"
            f"{binding['cross_layer_edges']}条跨层边中有{binding['cross_scs_below_threshold']}条低于"
            f"SCS阈值{binding['scs_threshold']}，最小SCS为{binding['min_cross_scs']}。"
        ),
        "",
        "## E05 社区划分对比（同一无向投影）",
        "",
    ]
    lines += _table(results["e05-community"]["methods"], "方法")
    lines += [
        "## E06 证据检索对比（银标准）",
        "",
    ]
    for label, rows in results["e06-retrieval"]["conditions"].items():
        lines += [f"### 条件：{label}", ""]
        lines += _table(rows, "方法")
    lines += ["### E07 检索侧消融（限定事项）", ""]
    lines += _table(results["e06-retrieval"]["ablation_matter_scoped"], "配置")
    lines += [
        "## E09 首错定位与计划修复（注入缺陷）",
        "",
        (
            f"参考案例 {results['e09-repair']['reference_cases']} 个，"
            f"步骤缺陷 {results['e09-repair']['step_defects']} 个，"
            f"事实缺陷 {results['e09-repair']['fact_defects']} 个；"
            f"首错位置精确命中 {results['e09-repair']['localisation']['exact']}/"
            f"{results['e09-repair']['localisation']['total']}。"
        ),
        "",
    ]
    lines += _table(results["e09-repair"]["methods"], "方法")
    lines += [
        "## E10 下一步推荐",
        "",
        (
            f"样本 {results['e10-next']['samples']} 个，平均可执行候选 "
            f"{results['e10-next']['mean_candidate_count']} 个，"
            f"违规推荐 {results['e10-next']['violating_recommendations']} 次。"
        ),
        "",
    ]
    lines += _table(results["e10-next"]["methods"], "排序方法")
    update = results["e11-update"]
    lines += [
        "## E11 知识更新一致性（离线副本）",
        "",
        (
            f"分别移除{len(update['scenarios'])}份来源文件并重建；"
            f"残留过期引用合计{update['total_residual_stale']}处。"
        ),
        "",
    ]
    lines += _table(
        {
            row["document"].rsplit("/", 1)[-1]: _flatten(
                {key: value for key, value in row.items() if key != "document"}
            )
            for row in update["scenarios"]
        },
        "移除文件",
    )
    return "\n".join(lines)


def main() -> None:
    results = {}
    for name, run in EXPERIMENTS.items():
        print(f"running {name} ...", file=sys.stderr)
        results[name] = run()
        write_result(name, results[name])
    built = snapshot("full")
    meta = {
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": _commit(),
        "python": platform.python_version(),
        "nodes": len(built["graph"]["nodes"]),
        "edges": len(built["graph"]["edges"]),
        "reference_cases": reference_report(),
    }
    write_result("run-meta", meta)
    (RESULT_DIR / "README.md").write_text(render(results, meta), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
