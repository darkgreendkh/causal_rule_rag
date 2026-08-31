from app.embedding import SentenceTransformerEmbedder


class FakeSentenceTransformer:
    def encode(self, texts: list[str], **options: object) -> "FakeArray":
        if options != {
            "normalize_embeddings": True,
            "convert_to_numpy": True,
            "show_progress_bar": False,
        }:
            raise AssertionError(f"unexpected encode options: {options}")
        return FakeArray([[0.1, 0.2] for _ in texts])


class FakeArray:
    def __init__(self, values: list[list[float]]) -> None:
        self._values = values

    def tolist(self) -> list[list[float]]:
        return self._values


def test_embedder_returns_normalized_serializable_vectors() -> None:
    embedder = SentenceTransformerEmbedder(
        "BAAI/bge-m3", model=FakeSentenceTransformer()
    )

    assert embedder.embed(["第一条", "第二条"]) == [[0.1, 0.2], [0.1, 0.2]]
