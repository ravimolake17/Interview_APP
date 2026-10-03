"""BGE-M3 embedding singleton for hybrid semantic skill matching."""

from __future__ import annotations

import logging
import threading
from typing import Any

import numpy as np

from agents.screening_agent.config import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_service: EmbeddingService | None = None


class EmbeddingService:
    """Load BAAI/bge-m3 once, batch-embed skill phrases, cache vectors."""

    def __init__(self) -> None:
        self._model: Any | None = None
        self._backend: str | None = None
        self._cache: dict[str, np.ndarray] = {}
        self._load_failed: bool = False
        self._load_error: str | None = None

    def is_loaded(self) -> bool:
        """True only when BGE-M3 is already in memory. Does not trigger a load."""
        return self._model is not None

    @property
    def model_name(self) -> str:
        return settings.ATS_SEMANTIC_MODEL

    def is_available(self) -> bool:
        if not settings.ATS_SEMANTIC_MATCHING_ENABLED or self._load_failed:
            return False
        try:
            import sentence_transformers  # noqa: F401
            return True
        except Exception as exc:
            logger.warning(
                "sentence-transformers unavailable (%s: %s); trying FlagEmbedding",
                type(exc).__name__,
                exc,
            )
        try:
            import FlagEmbedding  # noqa: F401
            return True
        except Exception as exc:
            self._load_failed = True
            self._load_error = str(exc)
            logger.warning(
                "Semantic embedding backends unavailable (%s); using rule-based skill matching.",
                type(exc).__name__,
            )
            return False

    def _load_with_sentence_transformers(self) -> Any:
        from sentence_transformers import SentenceTransformer

        logger.info(
            "Loading semantic embedding model via sentence-transformers: %s",
            self.model_name,
        )
        model = SentenceTransformer(self.model_name)
        self._backend = "sentence_transformers"
        return model

    def _load_with_flag_embedding(self) -> Any:
        from FlagEmbedding import BGEM3FlagModel

        logger.info(
            "Loading semantic embedding model via FlagEmbedding: %s",
            self.model_name,
        )
        model = BGEM3FlagModel(
            self.model_name,
            use_fp16=settings.ATS_SEMANTIC_USE_FP16,
        )
        self._backend = "flag_embedding"
        return model

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        if self._load_failed:
            raise RuntimeError(
                self._load_error or "Semantic embedding model previously failed to load."
            )

        with _lock:
            if self._model is not None:
                return self._model
            if self._load_failed:
                raise RuntimeError(
                    self._load_error
                    or "Semantic embedding model previously failed to load."
                )

            errors: list[str] = []
            # Prefer sentence-transformers: more stable with current transformers/torch.
            try:
                self._model = self._load_with_sentence_transformers()
                logger.info(
                    "Semantic embedding model ready (%s): %s",
                    self._backend,
                    self.model_name,
                )
                return self._model
            except Exception as exc:
                errors.append(f"sentence-transformers: {exc}")
                logger.warning(
                    "sentence-transformers BGE-M3 load failed (%s); trying FlagEmbedding",
                    type(exc).__name__,
                )

            try:
                self._model = self._load_with_flag_embedding()
                logger.info(
                    "Semantic embedding model ready (%s): %s",
                    self._backend,
                    self.model_name,
                )
                return self._model
            except Exception as exc:
                errors.append(f"FlagEmbedding: {exc}")
                self._load_failed = True
                self._load_error = "; ".join(errors)
                logger.exception(
                    "Semantic embedding model failed to load; "
                    "semantic matching will be disabled until restart."
                )
                raise RuntimeError(self._load_error) from exc

    def embed_texts(self, texts: list[str]) -> dict[str, np.ndarray]:
        """Return L2-normalized dense vectors keyed by original text."""
        cleaned = [" ".join(str(text).split()).strip() for text in texts if str(text).strip()]
        unique = list(dict.fromkeys(cleaned))
        if not unique:
            return {}

        missing = [text for text in unique if text not in self._cache]
        if missing:
            model = self._load_model()
            batch_size = settings.ATS_SEMANTIC_EMBED_BATCH_SIZE
            for start in range(0, len(missing), batch_size):
                batch = missing[start : start + batch_size]
                if self._backend == "sentence_transformers":
                    vectors = np.asarray(
                        model.encode(
                            batch,
                            batch_size=min(batch_size, len(batch)),
                            normalize_embeddings=True,
                            show_progress_bar=False,
                        ),
                        dtype=np.float32,
                    )
                else:
                    output = model.encode(
                        batch,
                        batch_size=min(batch_size, len(batch)),
                        max_length=512,
                    )
                    dense = output.get("dense_vecs")
                    if dense is None:
                        raise RuntimeError("BGE-M3 encode did not return dense_vecs.")
                    vectors = np.asarray(dense, dtype=np.float32)
                    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
                    vectors = vectors / np.clip(norms, 1e-9, None)

                for text, vector in zip(batch, vectors, strict=True):
                    self._cache[text] = np.asarray(vector, dtype=np.float32)

        return {text: self._cache[text] for text in unique if text in self._cache}

    @staticmethod
    def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
        return float(np.dot(left, right))


def get_embedding_service() -> EmbeddingService:
    global _service
    if _service is None:
        with _lock:
            if _service is None:
                _service = EmbeddingService()
    return _service
