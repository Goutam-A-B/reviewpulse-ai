"""bge-small-en-v1.5 via fastembed (ONNX, no PyTorch). Wired in Phase 2.

fastembed keeps the embedder small enough for a free host (EC-P0-06). Local and
free; no API key. The ONNX model is downloaded once and cached, then loaded
lazily on first embed(). Embeddings are deterministic (same text -> same vector).
"""
from __future__ import annotations

from app.config import Settings


class FastEmbedEmbedder:
    name = "fastembed"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.model = settings.embed_model
        self.dim = settings.embed_dim
        self._te = None

    def is_configured(self) -> bool:
        return self._settings.embed_dim > 0

    def _model(self):
        if self._te is None:
            from fastembed import TextEmbedding

            self._te = TextEmbedding(model_name=self.model)
        return self._te

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [[float(x) for x in v] for v in self._model().embed(list(texts))]
