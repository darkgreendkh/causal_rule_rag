from typing import Any


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, model: Any | None = None) -> None:
        self._model_name = model_name
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()
