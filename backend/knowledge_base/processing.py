from django.db import transaction
from django.conf import settings

from knowledge_base.chunking import chunk_text
from knowledge_base.embeddings import (
    EmbeddingServiceError,
    embed_texts,
    embedding_metadata,
)
from knowledge_base.models import DocumentChunk, KnowledgeDocument
from knowledge_base.services import extract_document_pages


class DocumentProcessingError(Exception):
    """Raised when extracted document text cannot be chunked and persisted."""


def process_document(document):
    """Replace all chunks for a document in one transaction."""
    try:
        with document.stored_file.open('rb') as stored_file:
            pages = extract_document_pages(stored_file, document.file_type)
        chunk_rows = []
        index = 0
        chunk_size = settings.RAG_CONFIG['CHUNK_SIZE']
        overlap = settings.RAG_CONFIG['CHUNK_OVERLAP']
        for page_text, page_number in pages:
            for text in chunk_text(
                page_text,
                chunk_size=chunk_size,
                overlap=overlap,
            ):
                chunk_rows.append(DocumentChunk(
                    document=document,
                    chunk_index=index,
                    text=text,
                    page_number=page_number,
                    character_count=len(text),
                ))
                index += 1
        if not chunk_rows:
            raise DocumentProcessingError('The document contains no text.')
        vectors = embed_texts([chunk.text for chunk in chunk_rows])
        embedding_model, embedding_dimension = embedding_metadata()
        for chunk, vector in zip(chunk_rows, vectors):
            chunk.embedding = vector.tolist()
            chunk.embedding_model = embedding_model
            chunk.embedding_dimension = embedding_dimension
        with transaction.atomic():
            DocumentChunk.objects.filter(document=document).delete()
            DocumentChunk.objects.bulk_create(chunk_rows)
            document.status = KnowledgeDocument.Status.PROCESSED
            document.error_message = ''
            document.save(update_fields=('status', 'error_message', 'updated_at'))
    except DocumentProcessingError:
        raise
    except EmbeddingServiceError as exc:
        raise DocumentProcessingError(
            'The document embeddings could not be generated.'
        ) from exc
    except Exception as exc:
        raise DocumentProcessingError('The document could not be processed.') from exc
