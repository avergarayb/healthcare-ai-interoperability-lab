"""Embedding boundary for institutional knowledge.

The pinned google-genai 2.24.0 call is client.models.embed_content.
This module does not generate text and does not select a fallback model.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

EMBEDDING_BATCH_SIZE = 16
EMBEDDING_TIMEOUT_MS = 30_000
MAX_VECTOR_DIMENSION = 4096


class EmbeddingUnavailable(Exception):
    reason = "embedding_unavailable"

    def __init__(self) -> None:
        super().__init__(self.reason)


class EmbeddingProvider(Protocol):
    @property
    def model_id(self) -> str:
        """Configured embedding model identity. Not a generation model."""

    def embed_texts(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        """Return one finite vector per text, in order."""


class GeminiEmbeddingProvider:
    """Dedicated embedding adapter. It is not the narrative Gemini provider."""

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key or not model or len(model) > 128:
            raise EmbeddingUnavailable()
        self._api_key = api_key
        self._model = model

    @property
    def model_id(self) -> str:
        return self._model

    def embed_texts(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        if not texts:
            return []
        if any(not isinstance(text, str) or text == "" for text in texts):
            raise EmbeddingUnavailable()
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(timeout=EMBEDDING_TIMEOUT_MS),
        )
        vectors: list[tuple[float, ...]] = []
        for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = list(texts[start : start + EMBEDDING_BATCH_SIZE])
            try:
                response = client.models.embed_content(model=self._model, contents=batch)
            except EmbeddingUnavailable:
                raise
            except Exception:
                raise EmbeddingUnavailable() from None
            embeddings = getattr(response, "embeddings", None)
            if not isinstance(embeddings, list) or len(embeddings) != len(batch):
                raise EmbeddingUnavailable()
            for item in embeddings:
                values = getattr(item, "values", None)
                if not values:
                    raise EmbeddingUnavailable()
                try:
                    vector = tuple(float(value) for value in values)
                except (TypeError, ValueError):
                    raise EmbeddingUnavailable() from None
                if not _usable_vector(vector):
                    raise EmbeddingUnavailable()
                vectors.append(vector)
        dimensions = {len(vector) for vector in vectors}
        if len(vectors) != len(texts) or len(dimensions) != 1:
            raise EmbeddingUnavailable()
        return vectors


def _usable_vector(vector: tuple[float, ...]) -> bool:
    if not 1 <= len(vector) <= MAX_VECTOR_DIMENSION:
        return False
    return all(isinstance(value, float) and value == value and abs(value) != float("inf") for value in vector)
