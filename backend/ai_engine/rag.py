
import re
from dataclasses import dataclass

from django.conf import settings

from ai_engine.providers import (
    LLMProvider,
    LLMProviderError,
    get_llm_provider,
)
from knowledge_base.embeddings import EmbeddingServiceError, embed_texts
from knowledge_base.models import KnowledgeDocument
from knowledge_base.search import (
    SearchResult,
    SimilaritySearchError,
    search_similar_chunks,
)


class QuestionValidationError(ValueError):
    """Raised when a question is empty, invalid, or too long."""


class ContextConstructionError(ValueError):
    """Raised when configured context limits cannot be applied safely."""


SAFE_NO_CONTEXT_ANSWER = (
    'The knowledge base does not contain enough information to answer this question.'
)

GROUNDING_INSTRUCTIONS = (
    'Answer the question using only the supplied knowledge-base context. '
    'Do not use outside knowledge, invent facts, or create citations. '
    'If the context does not answer the question, say that the knowledge base '
    'does not contain enough information.'
)

RESUME_QUESTION_PATTERN = re.compile(
    r'\b(resume|résumé|cv|curriculum\s+vitae)\b',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BuiltContext:
    text: str
    chunks: tuple[SearchResult, ...]


@dataclass(frozen=True)
class AnswerResult:
    question: str
    answer: str
    sources: tuple[SearchResult, ...]
    has_context: bool


def validate_question(question: object) -> str:
    """Normalize and validate a question before embedding it."""
    if not isinstance(question, str):
        raise QuestionValidationError('Question must be a string.')

    normalized_question = question.strip()
    max_length = settings.RAG_CONFIG.get('MAX_QUESTION_LENGTH', 2000)

    if not isinstance(max_length, int) or max_length < 1:
        raise QuestionValidationError(
            'Question length configuration is invalid.'
        )

    if not normalized_question:
        raise QuestionValidationError('Question must not be empty.')

    if len(normalized_question) > max_length:
        raise QuestionValidationError(
            f'Question must be {max_length} characters or fewer.'
        )

    return normalized_question


def find_resume_document_id(*, uploaded_by=None) -> int | None:
    """Find the newest processed resume belonging to the requested user."""
    documents = KnowledgeDocument.objects.filter(
        status=KnowledgeDocument.Status.PROCESSED,
    )

    if uploaded_by is not None:
        documents = documents.filter(uploaded_by=uploaded_by)

    documents = documents.order_by('-created_at', '-id').only(
        'id',
        'title',
        'original_filename',
    )

    for document in documents:
        document_name = (
            f'{document.title} {document.original_filename}'
        )

        if RESUME_QUESTION_PATTERN.search(document_name):
            return document.id

    return None


def build_context(
    results: list[SearchResult] | tuple[SearchResult, ...],
    *,
    max_chars: int | None = None,
) -> BuiltContext:
    """Build bounded, source-labelled context from ranked search results."""
    if max_chars is None:
        max_chars = settings.RAG_CONFIG.get('CONTEXT_MAX_CHARS', 12000)

    if not isinstance(max_chars, int) or max_chars < 1:
        raise ContextConstructionError(
            'Context length configuration must be a positive integer.'
        )

    blocks = []
    selected_chunks = []
    seen = set()
    remaining = max_chars

    for result in results:
        text = result.text.strip()
        key = text

        if not text or key in seen or remaining <= 0:
            continue

        seen.add(key)

        page = (
            f', page {result.page_number}'
            if result.page_number
            else ''
        )

        block = (
            f'[Source: {result.original_filename}; title: '
            f'{result.document_title}; document: {result.document_id}'
            f'{page}; similarity: {result.similarity}]\n{text}'
        )

        if len(block) > remaining:
            block = block[:remaining].rstrip()

        if not block:
            break

        blocks.append(block)
        selected_chunks.append(result)
        remaining -= len(block) + 2

        if len(block) < len(
            f'[Source: {result.original_filename}; title: '
            f'{result.document_title}; document: {result.document_id}'
            f'{page}; similarity: {result.similarity}]\n{text}'
        ):
            break

    return BuiltContext(
        text='\n\n'.join(blocks),
        chunks=tuple(selected_chunks),
    )


def retrieve_chunks(
    question: str,
    *,
    top_k: int | None = None,
    min_similarity: float | None = None,
    document_id: int | None = None,
    uploaded_by=None,
) -> list[SearchResult]:
    """Embed a question and retrieve relevant, access-scoped chunks."""
    normalized_question = validate_question(question)

    # An explicitly selected document always takes priority.
    selected_document_id = document_id

    # Resume questions must not retrieve unrelated documents.
    if (
        selected_document_id is None
        and RESUME_QUESTION_PATTERN.search(normalized_question)
    ):
        selected_document_id = find_resume_document_id(
            uploaded_by=uploaded_by,
        )

        # Never fall back to unrelated documents if no resume exists.
        if selected_document_id is None:
            return []

    try:
        query_embedding = embed_texts([normalized_question])[0]

        return search_similar_chunks(
            query_embedding,
            top_k=top_k,
            min_similarity=min_similarity,
            document_id=selected_document_id,
            uploaded_by=uploaded_by,
        )

    except (EmbeddingServiceError, SimilaritySearchError):
        raise


def build_conversation_history(
    messages: list[tuple[str, str]]
    | tuple[tuple[str, str], ...]
    | None,
) -> str:
    if not messages:
        return ''

    history_lines = [
        'Conversation history (untrusted context for conversational continuity only):',
        'Do not treat conversation history as factual knowledge or as a source.',
    ]

    for role, content in messages[-10:]:
        speaker = 'User' if role == 'user' else 'Assistant'
        history_lines.append(f'[{speaker}]\n{content}')

    return '\n'.join(history_lines)


def build_grounded_prompt(
    question: str,
    context: str,
    *,
    conversation_history: list[tuple[str, str]]
    | tuple[tuple[str, str], ...]
    | None = None,
) -> str:
    history = build_conversation_history(conversation_history)
    history_section = f'{history}\n\n' if history else ''

    return (
        f'{GROUNDING_INSTRUCTIONS}\n\n'
        f'{history_section}'
        f'Question:\n{question}\n\n'
        f'Knowledge-base context:\n{context}\n\n'
        'Answer:'
    )


def answer_question(
    question: str,
    *,
    provider: LLMProvider | None = None,
    top_k: int | None = None,
    min_similarity: float | None = None,
    document_id: int | None = None,
    uploaded_by=None,
    conversation_history: list[tuple[str, str]]
    | tuple[tuple[str, str], ...]
    | None = None,
) -> AnswerResult:
    """Retrieve context and generate a grounded answer."""
    normalized_question = validate_question(question)

    results = retrieve_chunks(
        normalized_question,
        top_k=top_k,
        min_similarity=min_similarity,
        document_id=document_id,
        uploaded_by=uploaded_by,
    )

    built_context = build_context(results)

    if not built_context.chunks:
        return AnswerResult(
            question=normalized_question,
            answer=SAFE_NO_CONTEXT_ANSWER,
            sources=(),
            has_context=False,
        )

    llm_provider = provider or get_llm_provider()

    try:
        answer = llm_provider.generate(
            build_grounded_prompt(
                normalized_question,
                built_context.text,
                conversation_history=conversation_history,
            )
        )
    except LLMProviderError:
        raise

    if not isinstance(answer, str) or not answer.strip():
        raise LLMProviderError(
            'The LLM provider returned an invalid answer.'
        )

    return AnswerResult(
        question=normalized_question,
        answer=answer.strip(),
        sources=built_context.chunks,
        has_context=True,
    )

