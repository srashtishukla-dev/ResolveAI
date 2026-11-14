from functools import lru_cache

import numpy as np
from django.conf import settings


class EmbeddingServiceError(RuntimeError):
    """Raised when local embedding generation is unavailable or invalid."""


def _embedding_config():
    config = settings.RAG_CONFIG
    dimensions = config['EMBEDDING_DIMENSIONS']
    if dimensions <= 0:
        raise EmbeddingServiceError('Embedding dimensions must be positive.')
    batch_size = config['EMBEDDING_BATCH_SIZE']
    if batch_size <= 0:
        raise EmbeddingServiceError('Embedding batch size must be positive.')
    return config['EMBEDDING_MODEL'], dimensions, batch_size


@lru_cache(maxsize=1)
def load_embedding_model():
    model_name, _, _ = _embedding_config()
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(model_name)
    except Exception as exc:
        raise EmbeddingServiceError(
            'The local embedding model is unavailable.'
        ) from exc


def embed_texts(texts):
    """Return normalized, finite float32 vectors for non-empty text input."""
    model_name, dimensions, batch_size = _embedding_config()
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise EmbeddingServiceError('Embedding input text must not be empty.')
    if not texts:
        return np.empty((0, dimensions), dtype=np.float32)
    try:
        vectors = load_embedding_model().encode(
            list(texts),
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
    except EmbeddingServiceError:
        raise
    except Exception as exc:
        raise EmbeddingServiceError(
            'The local embedding model could not encode the text.'
        ) from exc
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.shape != (len(texts), dimensions):
        raise EmbeddingServiceError('The embedding model returned invalid dimensions.')
    if not np.isfinite(vectors).all():
        raise EmbeddingServiceError('The embedding model returned invalid values.')
    return vectors


def embedding_metadata():
    model_name, dimensions, _ = _embedding_config()
    return model_name, dimensions
