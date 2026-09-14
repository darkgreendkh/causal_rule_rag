"""Versioned research snapshots and an inspectable Neo4j projection."""

import json
from pathlib import Path


class ResearchRepository:
    def __init__(self, driver, directory: Path, namespace="research"):
        self.driver = driver
        self.directory = directory
        self.namespace = namespace

    def load(self, profile: str) -> dict | None:
        records, _, _ = self.driver.execute_query(
            "MATCH (h:ResearchHead {profile: $profile, namespace:$namespace}) RETURN h.build_id AS id",
            profile=profile,
            namespace=self.namespace,
        )
        if not records:
            return None
        return json.loads(
            (self.directory / "snapshots" / f"{records[0]['id']}.json").read_text("utf-8")
        )

    def save(self, snapshot: dict) -> None:
        directory = self.directory / "snapshots"
        directory.mkdir(parents=True, exist_ok=True)
        bid, profile = snapshot["build_id"], snapshot["profile"]["id"]
        path = directory / f"{bid}.json"
        path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
        self.driver.execute_query(
            "CREATE CONSTRAINT research_node_key IF NOT EXISTS "
            "FOR (n:ResearchNode) REQUIRE n.key IS UNIQUE"
        )
        self.driver.execute_query(
            "CREATE CONSTRAINT research_head_scope IF NOT EXISTS "
            "FOR (n:ResearchHead) REQUIRE (n.namespace, n.profile) IS UNIQUE"
        )
        graph = snapshot["graph"]
        rows = [
            dict(
                n,
                key=f"{bid}:{n['id']}",
                payload=json.dumps(n, ensure_ascii=False),
                embedding=snapshot["vectors"].get(n["id"]),
            )
            for n in graph["nodes"]
        ]
        # New nodes are invisible to application queries until the head switches.
        for start in range(0, len(rows), 200):
            self.driver.execute_query(
                "UNWIND $rows AS row CREATE (n:ResearchNode {key:row.key, id:row.id, "
                "build_id:$bid, namespace:$namespace, profile:$profile, label:row.label, type:row.type, layer:row.layer, "
                "community_id:row.community_id, embedding:row.embedding, payload:row.payload})",
                rows=rows[start : start + 200],
                bid=bid,
                profile=profile,
                namespace=self.namespace,
            )
        edge_rows = [
            dict(
                e,
                source_key=f"{bid}:{e['source']}",
                target_key=f"{bid}:{e['target']}",
                payload=json.dumps(e, ensure_ascii=False),
            )
            for e in graph["edges"]
        ]
        for start in range(0, len(edge_rows), 400):
            self.driver.execute_query(
                "UNWIND $rows AS row MATCH (a:ResearchNode {key:row.source_key}), "
                "(b:ResearchNode {key:row.target_key}) CREATE (a)-[:RESEARCH_LINK "
                "{id:row.id, type:row.type, rpc:row.rpc, scs:row.scs, payload:row.payload}]->(b)",
                rows=edge_rows[start : start + 400],
            )
        with self.driver.session() as session:
            session.execute_write(
                self._activate, bid, profile, snapshot["created_at"], self.namespace
            )

    @staticmethod
    def _activate(tx, bid, profile, created, namespace):
        previous = tx.run(
            "MATCH (h:ResearchHead {profile:$profile, namespace:$namespace}) "
            "RETURN h.build_id AS bid",
            profile=profile,
            namespace=namespace,
        )
        old_ids = [r["bid"] for r in previous]
        tx.run(
            "MATCH (s:KnowledgeSnapshot {profile:$profile, namespace:$namespace, active:true}) SET s.active=false",
            profile=profile,
            namespace=namespace,
        ).consume()
        tx.run(
            "CREATE (:KnowledgeSnapshot {build_id:$bid, profile:$profile, namespace:$namespace, created_at:$created, "
            "active:true}) MERGE (h:ResearchHead {profile:$profile, namespace:$namespace}) SET h.build_id=$bid",
            bid=bid,
            profile=profile,
            namespace=namespace,
            created=created,
        ).consume()
        tx.run(
            "MATCH (n:ResearchNode {namespace:$namespace, profile:$profile}) "
            "WHERE n.build_id IN $old_ids AND n.build_id <> $bid DETACH DELETE n",
            namespace=namespace,
            profile=profile,
            bid=bid,
            old_ids=old_ids,
        ).consume()

    def invalidate(self, reason: str) -> None:
        with self.driver.session() as session:
            session.execute_write(self._invalidate, reason, self.namespace)

    @staticmethod
    def _invalidate(tx, reason, namespace):
        tx.run(
            "MATCH (s:KnowledgeSnapshot {active:true, namespace:$namespace}) SET s.active=false, s.invalidated_reason=$reason",
            reason=reason,
            namespace=namespace,
        ).consume()
        tx.run(
            "MATCH (h:ResearchHead {namespace:$namespace}) DELETE h", namespace=namespace
        ).consume()
        # Snapshots on disk remain an audit record; no obsolete live graph is retained.
        tx.run(
            "MATCH (n:ResearchNode {namespace:$namespace}) DETACH DELETE n", namespace=namespace
        ).consume()

    def log(self, event: dict) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / "runs.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
