from pathlib import Path

from django.core.exceptions import ValidationError
from pypdf import PdfReader


class DocumentExtractionError(ValidationError):
    """Raised when a supported document cannot be safely extracted."""


def _read_pdf_pages(uploaded_file):
    uploaded_file.seek(0)
    try:
        reader = PdfReader(uploaded_file)
        pages = [
            (page.extract_text() or '', page_number)
            for page_number, page in enumerate(reader.pages, start=1)
        ]
    except Exception as exc:
        raise DocumentExtractionError('The PDF could not be read.') from exc
    if not any(text.strip() for text, _ in pages):
        raise DocumentExtractionError('The PDF does not contain extractable text.')
    return pages


def _read_text_pages(uploaded_file):
    uploaded_file.seek(0)
    try:
        text = uploaded_file.read().decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise DocumentExtractionError(
            'The TXT file must use UTF-8 encoding.'
        ) from exc
    if not text.strip():
        raise DocumentExtractionError('The document is empty.')
    return [(text, None)]


def extract_document_pages(uploaded_file, file_type):
    if file_type == 'PDF':
        return _read_pdf_pages(uploaded_file)
    if file_type == 'TXT':
        return _read_text_pages(uploaded_file)
    raise DocumentExtractionError('Unsupported document type.')


def extract_document_text(uploaded_file, file_type):
    pages = extract_document_pages(uploaded_file, file_type)
    text = '\n'.join(page_text.strip() for page_text, _ in pages).strip()
    if not text:
        raise DocumentExtractionError('The document is empty.')
    return text


def validate_upload(uploaded_file, max_size):
    if not uploaded_file or not uploaded_file.name:
        raise DocumentExtractionError('A document file is required.')
    if uploaded_file.size == 0:
        raise DocumentExtractionError('The document is empty.')
    if uploaded_file.size > max_size:
        raise DocumentExtractionError('The document exceeds the maximum size.')

    extension = Path(uploaded_file.name).suffix.lower()
    uploaded_file.seek(0)
    header = uploaded_file.read(5)
    uploaded_file.seek(0)
    if extension == '.pdf' and header != b'%PDF-':
        raise DocumentExtractionError('The file is not a valid PDF.')
    if extension == '.txt' and b'\x00' in uploaded_file.read(4096):
        raise DocumentExtractionError('The TXT file contains binary data.')
    uploaded_file.seek(0)

    if extension not in {'.pdf', '.txt'}:
        raise DocumentExtractionError('Only PDF and TXT files are supported.')
    return extension[1:].upper()
