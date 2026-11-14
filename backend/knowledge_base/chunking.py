import re


def _validate_settings(chunk_size, overlap):
    if chunk_size <= 0:
        raise ValueError('chunk_size must be greater than zero.')
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError('overlap must be at least zero and smaller than chunk_size.')


def _end_boundary(text, start, limit):
    end = min(start + limit, len(text))
    if end == len(text):
        return end

    sentence_boundary = max(
        text.rfind('. ', start + 1, end),
        text.rfind('! ', start + 1, end),
        text.rfind('? ', start + 1, end),
        text.rfind('\n\n', start + 1, end),
    )
    if sentence_boundary > start:
        return sentence_boundary + 1

    whitespace_boundary = text.rfind(' ', start + 1, end)
    if whitespace_boundary > start:
        return whitespace_boundary
    return end


def _overlap_start(text, end, overlap):
    candidate = max(0, end - overlap)
    if candidate == 0:
        return candidate
    boundary = text.find(' ', candidate, min(end, candidate + 100))
    if boundary != -1 and boundary < end:
        return boundary + 1
    return candidate


def chunk_text(text, chunk_size=2000, overlap=200):
    """Split text by readable boundaries using character-based sizing.

    Character sizing is used instead of tokens to avoid adding a tokenizer
    dependency. Chunk limits are approximate token equivalents and preserve
    whitespace/sentence boundaries where possible.
    """
    _validate_settings(chunk_size, overlap)
    if not text or not text.strip():
        return []

    normalized = re.sub(r'[ \t]+', ' ', text.strip())
    chunks = []
    start = 0
    while start < len(normalized):
        end = _end_boundary(normalized, start, chunk_size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        next_start = _overlap_start(normalized, end, overlap)
        if next_start <= start:
            next_start = end
        start = next_start
    return chunks
