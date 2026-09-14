from copy import deepcopy

DEFAULTS = {
    "seed": 42, "rpc_threshold": 0.7, "scs_threshold": 0.7,
    "strong_threshold": 0.85, "community_levels": 3, "community_top_k": 3,
    "max_hops": 6, "max_candidates": 100, "evidence_limit": 8, "max_states": 5000,
    "rpc": True, "scs": True, "macro": True, "micro": True,
    "causal_constraints": True, "semantic": True, "entropy": True,
    "rule_validation": True, "evidence_chain": True, "resolution": 1.0,
}

PROFILES = {
    "full": ("完整方法", {}),
    "without_rpc": ("移除RPC筛选与评分", {"rpc": False}),
    "without_scs": ("移除SCS跨层筛选", {"scs": False}),
    "without_macro": ("移除宏观图层", {"macro": False}),
    "without_micro": ("移除微观图层", {"micro": False}),
    "without_causal_constraints": ("移除因果社区硬约束", {"causal_constraints": False}),
    "without_semantic": ("移除路径语义评分", {"semantic": False}),
    "without_entropy": ("移除路径信息熵项", {"entropy": False}),
    "without_rule_validation": ("移除检索规则过滤", {"rule_validation": False}),
    "without_evidence_chain": ("移除生成阶段有序证据链", {"evidence_chain": False}),
}


def get_profile(name: str = "full") -> dict:
    if name not in PROFILES:
        raise ValueError(f"未知研究配置：{name}")
    result = deepcopy(DEFAULTS)
    result.update(PROFILES[name][1])
    result.update(id=name, label=PROFILES[name][0])
    return result


def list_profiles() -> list[dict]:
    return [{"id": key, "label": item[0], "description": "未调优的工程配置；不代表实验结论"}
            for key, item in PROFILES.items()]
