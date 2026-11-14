from dataclasses import dataclass

import numpy as np
from django.conf import settings
from django.db import connection
from pgvector.django import CosineDistance

from knowledge_base.models import DocumentChunk, KnowledgeDocument


class SimilaritySearchError(RuntimeError):
    """Raised when similarity search cannot be completed safely."""


@dataclass(frozen=True)
class SearchResult:
    chunk_id: int
    document_id: int
    document_title: str
    original_filename: str
    chunk_index: int
    page_number: int | None
    text: str
    similarity: float


def _validated_options(top_k=None, min_similarity=None):
    configured_top_k = settings.RAG_CONFIG.get('RETRIEVAL_TOP_K', 5)
    configured_threshold = settings.RAG_CONFIG.get(
        'RETRIEVAL_MIN_SIMILARITY',
        0.0,
    )
    top_k = configured_top_k if top_k is None else top_k
    min_similarity = (
        configured_threshold
        if min_similarity is None
        else min_similarity
    )
    if not isinstance(top_k, int) or not 1 <= top_k <= 100:
        raise SimilaritySearchError('top_k must be an integer between 1 and 100.')
    if not isinstance(min_similarity, (int, float)) or not 0 <= min_similarity <= 1:
        raise SimilaritySearchError(
            'min_similarity must be a number between 0 and 1.'
        )
    return top_k, float(min_similarity)


def _validate_query_embedding(query_embedding):
    values = np.asarray(query_embedding, dtype=np.float32)
    dimensions = settings.RAG_CONFIG['EMBEDDING_DIMENSIONS']
    if values.shape != (dimensions,):
        raise SimilaritySearchError('The query embedding has invalid dimensions.')
    if not np.isfinite(values).all() or not np.any(values):
        raise SimilaritySearchError('The query embedding is invalid.')
    norm = np.linalg.norm(values)
    if not norm:
        raise SimilaritySearchError('The query embedding is invalid.')
    return values / norm


def _result(chunk, similarity):
    return SearchResult(
        chunk_id=chunk.pk,
        document_id=chunk.document_id,
        document_title=chunk.document.title,
        original_filename=chunk.document.original_filename,
        chunk_index=chunk.chunk_index,
        page_number=chunk.page_number,
        text=chunk.text,
        similarity=round(float(similarity), 6),
    )


def _base_queryset(document_id=None, uploaded_by=None):
    queryset = DocumentChunk.objects.select_related('document').filter(
        embedding__isnull=False,
        document__status=KnowledgeDocument.Status.PROCESSED,
    )
    if document_id is not None:
        queryset = queryset.filter(document_id=document_id)
    if uploaded_by is not None:
        queryset = queryset.filter(document__uploaded_by=uploaded_by)
    return queryset


def _numpy_search(query_embedding, top_k, min_similarity, document_id, uploaded_by):
    chunks = list(_base_queryset(document_id, uploaded_by))
    scored = []
    for chunk in chunks:
        vector = np.asarray(chunk.embedding, dtype=np.float32)
        if vector.shape != query_embedding.shape or not np.isfinite(vector).all():
            continue
        norm = np.linalg.norm(vector)
        if not norm:
            continue
        similarity = float(np.dot(query_embedding, vector / norm))
        if similarity >= min_similarity:
            scored.append((similarity, chunk))
    scored.sort(key=lambda item: (-item[0], item[1].chunk_index))
    return [_result(chunk, score) for score, chunk in scored[:top_k]]


def _pgvector_search(query_embedding, top_k, min_similarity, document_id, uploaded_by):
    queryset = _base_queryset(document_id, uploaded_by).annotate(
        similarity=1 - CosineDistance('embedding', query_embedding.tolist()),
    ).filter(
        similarity__gte=min_similarity,
    ).order_by(
        '-similarity',
        'document_id',
        'chunk_index',
    )[:top_k]
    return [_result(chunk, chunk.similarity) for chunk in queryset]


def search_similar_chunks(
    query_embedding,
    *,
    top_k=None,
    min_similarity=None,
    document_id=None,
    uploaded_by=None,
):
    """Return ranked chunks using pgvector on PostgreSQL or NumPy elsewhere."""
    query_embedding = _validate_query_embedding(query_embedding)
    top_k, min_similarity = _validated_options(top_k, min_similarity)
    if connection.vendor == 'postgresql':
        try:
            return _pgvector_search(
                query_embedding,
                top_k,
                min_similarity,
                document_id,
                uploaded_by,
            )
        except Exception as exc:
            raise SimilaritySearchError(
                'PostgreSQL vector search could not be completed.'
            ) from exc
    return _numpy_search(
        query_embedding,
        top_k,
        min_similarity,
        document_id,
        uploaded_by,
    )
