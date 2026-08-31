from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from app.config import Settings


class Neo4jStore:
    def __init__(self, settings: Settings) -> None:
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def health(self) -> bool:
        try:
            self._driver.verify_connectivity()
        except (Neo4jError, OSError):
            return False
        return True

    def close(self) -> None:
        self._driver.close()
