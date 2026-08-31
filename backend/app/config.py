from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "change-me"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    embedding_model: str = "BAAI/bge-m3"
    uploads_dir: Path = PROJECT_ROOT / "data/uploads"
    cors_origins: list[str] = ["http://localhost:5173"]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)
