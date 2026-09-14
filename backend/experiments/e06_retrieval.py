"""E06/E07: evidence retrieval comparison and retrieval-side ablations.

The reference evidence for a query is the set of source units cited by that matter's
reviewed rules and actions. That mapping is a silver standard produced during
implementation, not independent annotation, and the graph modes were built from the
same citations, so the comparison favours them by construction (see 6.7).
"""

import math
import re
import time
from collections import Counter, defaultdict

import numpy as np

from app.research import ResearchService
from app.research_profiles import get_profile
from experiments.harness import (
    CACHE_DIR,
    DATA_DIR,
    corpus,
    embed_queries,
    snapshot,
    vectors,
    write_result,
)

TEMPLATES = ("办理{name}需要满足哪些条件？", "{name}的申请材料和办理步骤是什么？")
TOP_K = 8


class _OfflineRepository:
    def __init__(self, snapshots: dict):
        self._snapshots = snapshots

    def load(self, profile):
        return self._snapshots.get(profile)

    def save(self, snapshot):
        self._snapshots[snapshot["profile"]["id"]] = snapshot

    def invalidate(self, reason):  # experiments never mutate the live knowledge base
        pass

    def log(self, entry):
        pass


class _CachedEmbedder:
    _model_name = "BAAI/bge-m3"

    def __init__(self, queries: dict):
        self._queries = queries

    def embed(self, texts):
        return [self._queries[text].tolist() for text in texts]


class _StubChat:
    def complete(self, system, user):
        return "（检索实验未调用生成模型）"


def _service(profile_names: tuple[str, ...], queries: dict) -> ResearchService:
    snapshots = {}
    for name in profile_names:
        built = snapshot(name)
        snapshots[name] = {
            "build_id": f"offline-{name}",
            "profile": built["profile"],
            "corpus": built["corpus"],
            "graph": built["graph"],
            "vectors": {key: value.tolist() for key, value in vectors().items()},
            "corpus_fingerprint": "offline",
            "source_files": {},
        }
    return ResearchService(
        _OfflineRepository(snapshots), _CachedEmbedder(queries), _StubChat(), DATA_DIR, CACHE_DIR
    )


def _tokens(text: str) -> list[str]:
    clean = re.sub(r"\s+", "", text)
    return [clean[i : i + 2] for i in range(len(clean) - 1)] or [clean]


class _BM25:
    def __init__(self, units: list[dict], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.ids = [u["id"] for u in units]
        self.docs = [Counter(_tokens(u["title"] + u["text"])) for u in units]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.average = sum(self.lengths) / max(1, len(self.lengths))
        postings = defaultdict(int)
        for doc in self.docs:
            for term in doc:
                postings[term] += 1
        self.idf = {
            term: math.log(1 + (len(self.docs) - n + 0.5) / (n + 0.5)) for term, n in postings.items()
        }

    def search(self, query: str, k: int) -> list[str]:
        terms = Counter(_tokens(query))
        scored = []
        for i, doc in enumerate(self.docs):
            score = 0.0
            for term in terms:
                if term not in doc:
                    continue
                frequency = doc[term]
                denominator = frequency + self.k1 * (
                    1 - self.b + self.b * self.lengths[i] / self.average
                )
                score += self.idf[term] * frequency * (self.k1 + 1) / denominator
            if score > 0:
                scored.append((score, self.ids[i]))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [uid for _, uid in scored[:k]]


def _queries() -> list[dict]:
    source = corpus()
    rules = defaultdict(list)
    for rule in source["rules"]:
        if rule["status"] == "active":
            rules[rule["matter_id"]].append(rule)
    actions = defaultdict(list)
    for action in source["actions"]:
        actions[action["matter_id"]].append(action)
    result = []
    for matter in source["matters"]:
        gold = {
            e["unit_id"]
            for item in rules[matter["id"]] + actions[matter["id"]]
            for e in item["evidence"]
        }
        if not gold:
            continue
        region = "武汉" if any(r["scope"].get("region") != "全国" for r in rules[matter["id"]]) else "全国"
        for template in TEMPLATES:
            result.append(
                {
                    "question": template.format(name=matter["name"]),
                    "matter_id": matter["id"],
                    "category": matter["category"],
                    "region": region,
                    "gold": sorted(gold),
                }
            )
    return result


def _metrics(ranked: list[str], gold: list[str], k: int = TOP_K) -> dict:
    top = ranked[:k]
    hits = [uid in gold for uid in top]
    relevant = sum(hits)
    rank = next((i + 1 for i, hit in enumerate(hits) if hit), 0)
    dcg = sum(hit / math.log2(i + 2) for i, hit in enumerate(hits))
    ideal = sum(1 / math.log2(i + 2) for i in range(min(k, len(gold))))
    return {
        "precision": relevant / max(1, len(top)),
        "recall": relevant / len(gold),
        "rr": 1 / rank if rank else 0.0,
        "ndcg": dcg / ideal if ideal else 0.0,
        "complete": float(set(gold) <= set(top)),
    }


LABELS = {
    "precision": f"P@{TOP_K}",
    "recall": f"R@{TOP_K}",
    "rr": "MRR",
    "ndcg": f"nDCG@{TOP_K}",
    "complete": "完整证据率",
}


def _aggregate(rows: list[dict], seconds: float, empty: int, count: int) -> dict:
    result = {
        label: round(sum(row[key] for row in rows) / max(1, len(rows)), 4)
        for key, label in LABELS.items()
    }
    result["空结果数"] = empty
    result["平均耗时毫秒"] = round(seconds * 1000 / max(1, count), 1)
    return result


def run(profiles: tuple[str, ...] = ("full",)) -> dict:
    queries = _queries()
    texts = sorted({q["question"] for q in queries})
    query_vectors = embed_queries(texts)
    ablations = (
        "full",
        "without_semantic",
        "without_entropy",
        "without_rpc",
        "without_causal_constraints",
        "without_rule_validation",
    )
    service = _service(tuple(dict.fromkeys(profiles + ablations)), query_vectors)
    source = corpus()
    bm25 = _BM25(source["units"])
    unit_ids = {u["id"] for u in source["units"]}

    scoped_units = {
        m["id"]: set(m["source_unit_ids"]) for m in source["matters"]
    }

    def evaluate(retrieve):
        rows, empty, seconds = [], 0, 0.0
        for query in queries:
            started = time.perf_counter()
            ranked = [uid for uid in retrieve(query) if uid in unit_ids]
            seconds += time.perf_counter() - started
            empty += not ranked
            rows.append(_metrics(ranked, query["gold"]))
        return _aggregate(rows, seconds, empty, len(queries))

    def mode(name, profile="full", scoped=True):
        def retrieve(query):
            result = service.answer(
                {
                    "question": query["question"],
                    "mode": name,
                    "matter_id": query["matter_id"] if scoped else None,
                    "region": query["region"],
                    "profile": profile,
                }
            )
            return [s["chunk_id"] for s in result["sources"]]

        return retrieve

    def bm25_search(scoped):
        def retrieve(query):
            allowed = scoped_units[query["matter_id"]] if scoped else None
            ranked = bm25.search(query["question"], TOP_K if not scoped else len(unit_ids))
            if allowed is not None:
                ranked = [uid for uid in ranked if uid in allowed][:TOP_K]
            return ranked

        return retrieve

    conditions = {}
    for label, scoped in (("限定事项", True), ("不限定事项", False)):
        conditions[label] = {
            "BM25": evaluate(bm25_search(scoped)),
            "向量检索": evaluate(mode("vector", scoped=scoped)),
            "普通图扩展": evaluate(mode("hybrid", scoped=scoped)),
            "有向约束检索（本文）": evaluate(mode("causal", scoped=scoped)),
        }
    ablation = {
        get_profile(name)["label"]: evaluate(mode("causal", name)) for name in ablations
    }
    return {
        "queries": len(queries),
        "matters": len({q["matter_id"] for q in queries}),
        "mean_gold_size": round(float(np.mean([len(q["gold"]) for q in queries])), 2),
        "top_k": TOP_K,
        "conditions": conditions,
        "ablation_matter_scoped": ablation,
    }


if __name__ == "__main__":
    write_result("e06-retrieval", run())
