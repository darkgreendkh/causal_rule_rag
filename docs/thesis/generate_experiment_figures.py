"""Draw chapter 6 result figures from the JSON written by backend/experiments/run_all.py.

Usage: D:/anaconda/python.exe docs/thesis/generate_experiment_figures.py
Only experiments that have actually run get a figure; E01-E03 and E08 keep the
pending-annotation placeholder.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / 'experiments'
FIGURES = ROOT / 'figures'
INK = '#1f2933'
SERIES = ['#2f5d8a', '#c07c3a', '#5a8f6b', '#8a5a8f', '#9a9a9a']

plt.rcParams.update({
    'font.sans-serif': ['SimHei', 'Microsoft YaHei'],
    'axes.unicode_minus': False,
    'font.size': 9,
    'axes.edgecolor': INK,
    'axes.labelcolor': INK,
    'text.color': INK,
    'xtick.color': INK,
    'ytick.color': INK,
    'figure.dpi': 200,
})


def load(name):
    return json.loads((RESULTS / f'{name}.json').read_text('utf-8'))


def finish(fig, name):
    for axis in fig.axes:
        axis.spines['top'].set_visible(False)
        axis.spines['right'].set_visible(False)
        axis.grid(axis='y', color='#d8dee4', linewidth=0.6)
        axis.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(FIGURES / f'{name}.png', bbox_inches='tight')
    plt.close(fig)


def fig_e04():
    data = load('e04-graph')['profiles']
    labels = {'full': '完整方法', 'without_rpc': '去RPC', 'without_scs': '去SCS',
              'without_macro': '去宏观层', 'without_micro': '去微观层'}
    names = [labels[k] for k in data]
    fig, axis = plt.subplots(figsize=(6.4, 3.0))
    width, offsets = 0.27, (-1, 0, 1)
    keys = [('nodes', '节点'), ('edges', '边'), ('cross_layer_edges', '跨层边')]
    for (key, label), offset, color in zip(keys, offsets, SERIES):
        values = [data[k][key] for k in data]
        bars = axis.bar([i + offset * width for i in range(len(names))], values,
                        width, label=label, color=color)
        axis.bar_label(bars, fmt='%d', fontsize=7, padding=1)
    axis.set_xticks(range(len(names)), names)
    axis.set_ylabel('数量')
    axis.legend(frameon=False, ncols=3, loc='upper right')
    axis.set_ylim(0, max(d['edges'] for d in data.values()) * 1.25)
    finish(fig, 'fig6-4-graph-ablation')


def fig_e05():
    data = load('e05-community')['methods']
    names = list(data)
    fig, axis = plt.subplots(figsize=(6.4, 3.0))
    width = 0.35
    for (key, label), offset, color in zip(
            [('modularity', '模块度'), ('matter_purity', '事项纯度')], (-0.5, 0.5), SERIES):
        bars = axis.bar([i + offset * width for i in range(len(names))],
                        [data[n][key] for n in names], width, label=label, color=color)
        axis.bar_label(bars, fmt='%.3f', fontsize=7, padding=1)
    axis.set_xticks(range(len(names)), names, fontsize=8)
    axis.set_ylabel('取值')
    axis.set_ylim(0, 1.15)
    twin = axis.twinx()
    twin.plot(range(len(names)), [data[n]['strong_edge_keep_rate'] for n in names],
              marker='o', color=SERIES[2], label='强依赖同群率')
    twin.set_ylabel('强依赖同群率')
    twin.set_ylim(-0.05, 1.08)
    twin.spines['top'].set_visible(False)
    handles = axis.get_legend_handles_labels()[0] + twin.get_legend_handles_labels()[0]
    axis.legend(handles, ['模块度', '事项纯度', '强依赖同群率'], frameon=False,
                ncols=3, loc='lower center', bbox_to_anchor=(0.5, 1.01))
    finish(fig, 'fig6-5-community')


def fig_e06():
    data = load('e06-retrieval')['conditions']
    names = list(next(iter(data.values())))
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.0), sharey=True)
    for axis, (condition, rows) in zip(axes, data.items()):
        width = 0.35
        for (key, label), offset, color in zip(
                [('R@8', 'R@8'), ('nDCG@8', 'nDCG@8')], (-0.5, 0.5), SERIES):
            bars = axis.bar([i + offset * width for i in range(len(names))],
                            [rows[n][key] for n in names], width, label=label, color=color)
            axis.bar_label(bars, fmt='%.2f', fontsize=7, padding=1)
        axis.set_xticks(range(len(names)), ['BM25', '向量', '普通图', '本文'], fontsize=8)
        axis.set_title(condition, fontsize=9)
        axis.set_ylim(0, 1.05)
    axes[0].set_ylabel('取值')
    axes[0].legend(frameon=False, ncols=2, loc='upper left')
    finish(fig, 'fig6-6-retrieval')


def fig_e07():
    data = load('e06-retrieval')['ablation_matter_scoped']
    base = data['完整方法']
    names = [n for n in data if n != '完整方法']
    fig, axis = plt.subplots(figsize=(6.4, 3.0))
    width = 0.35
    for (key, label), offset, color in zip(
            [('R@8', 'R@8'), ('完整证据率', '完整证据率')], (-0.5, 0.5), SERIES):
        values = [data[n][key] - base[key] for n in names]
        bars = axis.bar([i + offset * width for i in range(len(names))], values,
                        width, label=label, color=color)
        axis.bar_label(bars, fmt='%+.3f', fontsize=7, padding=2)
    axis.axhline(0, color=INK, linewidth=0.8)
    axis.set_xticks(range(len(names)), [n.replace('移除', '去') for n in names], fontsize=8)
    axis.set_ylabel('相对完整方法的差值')
    axis.legend(frameon=False, ncols=2, loc='upper right')
    finish(fig, 'fig6-7-path-ablation')


def fig_e09():
    data = load('e09-repair')['methods']
    names = [n for n in data if data[n]['mean_edit_cost_by_kind']]
    kinds = [('delete', '删除步骤'), ('swap', '次序交换'), ('premature', '步骤提前')]
    bounds = {'delete': 1, 'swap': 2, 'premature': 1}
    fig, axis = plt.subplots(figsize=(6.4, 3.0))
    width = 0.26
    for i, (name, color) in enumerate(zip(names, SERIES)):
        values = [data[name]['mean_edit_cost_by_kind'][k] for k, _ in kinds]
        bars = axis.bar([j + (i - 1) * width for j in range(len(kinds))], values,
                        width, label=name, color=color)
        axis.bar_label(bars, fmt='%.2f', fontsize=7, padding=1)
    for j, (key, _) in enumerate(kinds):
        axis.plot([j - 1.6 * width, j + 1.6 * width], [bounds[key]] * 2,
                  linestyle='--', color=INK, linewidth=1)
    axis.set_xticks(range(len(kinds)), [label for _, label in kinds])
    axis.set_ylabel('平均单位编辑代价')
    axis.set_ylim(0, 2.3)
    axis.legend(frameon=False, ncols=3, loc='lower center', bbox_to_anchor=(0.5, 1.01),
                fontsize=8)
    axis.text(1.0, bounds['swap'] + 0.06, '注入代价上界', fontsize=7, ha='center')
    finish(fig, 'fig6-9-repair-cost')


def fig_e10():
    after = load('e10-next')
    before = load('e10-next-before-fix')
    names = list(after['methods'])
    fig, axis = plt.subplots(figsize=(6.0, 3.0))
    width = 0.35
    for (source, label), offset, color in zip(
            [(before, '修正前'), (after, '修正后')], (-0.5, 0.5), SERIES):
        bars = axis.bar([i + offset * width for i in range(len(names))],
                        [source['methods'][n]['Top-1命中率'] for n in names],
                        width, label=label, color=color)
        axis.bar_label(bars, fmt='%.3f', fontsize=7, padding=1)
    axis.set_xticks(range(len(names)), ['目录顺序', '字典序', '语义排序'], fontsize=8)
    axis.set_ylabel('Top-1命中率')
    axis.set_ylim(0, 1.1)
    axis.legend(frameon=False, ncols=2, loc='upper left')
    axis.set_title(
        f"平均候选数 {before['mean_candidate_count']} → {after['mean_candidate_count']}",
        fontsize=9)
    finish(fig, 'fig6-10-next-step')


def fig_e11():
    rows = load('e11-update')['scenarios']
    fig, axis = plt.subplots(figsize=(6.0, 3.0))
    axis.scatter([r['removed_units'] for r in rows], [r['edges_removed'] for r in rows],
                 s=[20 + 6 * r['rules_removed'] for r in rows], color=SERIES[0], zorder=3)
    for row in rows:
        axis.annotate(row['document'].rsplit('/', 1)[-1].replace('.txt', '')[:14],
                      (row['removed_units'], row['edges_removed']),
                      textcoords='offset points', xytext=(4, 4), fontsize=7)
    axis.set_xlabel('移除的条款单元数')
    axis.set_ylabel('连带失效的边数')
    axis.set_title('点面积表示失效规则数', fontsize=9)
    finish(fig, 'fig6-11-update')


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    for draw in (fig_e04, fig_e05, fig_e06, fig_e07, fig_e09, fig_e10, fig_e11):
        draw()
    print(json.dumps({'figures': sorted(p.name for p in FIGURES.glob('fig6-*.png'))},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
