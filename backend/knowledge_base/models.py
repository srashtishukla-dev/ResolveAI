from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from pgvector.django import VectorField


class KnowledgeDocument(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        PROCESSED = 'PROCESSED', 'Processed'
        FAILED = 'FAILED', 'Failed'

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='knowledge_documents',
    )
    title = models.CharField(max_length=255, default='')
    original_filename = models.CharField(max_length=255)
    stored_file = models.FileField(upload_to='knowledge_base/%Y/%m/%d/')
    file_type = models.CharField(max_length=10)
    file_size = models.PositiveBigIntegerField(
        validators=[MinValueValidator(1)]
    )
    sha256 = models.CharField(max_length=64, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    extracted_text = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('uploaded_by', 'created_at')),
            models.Index(fields=('status', 'created_at')),
        ]

    def __str__(self):
        return self.original_filename


class DocumentChunk(models.Model):
    document = models.ForeignKey(
        KnowledgeDocument,
        on_delete=models.CASCADE,
        related_name='chunks',
    )
    chunk_index = models.PositiveIntegerField()
    text = models.TextField()
    page_number = models.PositiveIntegerField(null=True, blank=True)
    character_count = models.PositiveIntegerField(default=0)
    start_offset = models.PositiveIntegerField(null=True, blank=True)
    end_offset = models.PositiveIntegerField(null=True, blank=True)
    token_count = models.PositiveIntegerField(null=True, blank=True)
    embedding_model = models.CharField(max_length=255, blank=True)
    embedding_dimension = models.PositiveIntegerField(null=True, blank=True)
    embedding = VectorField(
        dimensions=384,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('document', 'chunk_index')
        constraints = [
            models.UniqueConstraint(
                fields=('document', 'chunk_index'),
                name='unique_document_chunk_index',
            ),
        ]
        indexes = [
            models.Index(fields=('document', 'chunk_index')),
        ]

    def __str__(self):
        return f'{self.document_id}:{self.chunk_index}'
