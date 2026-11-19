import hashlib
import uuid

from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework import serializers

from knowledge_base.models import DocumentChunk, KnowledgeDocument
from knowledge_base.services import (
    DocumentExtractionError,
    extract_document_text,
    validate_upload,
)


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    title = serializers.CharField(
        max_length=255,
        allow_blank=False,
        required=True,
    )
    file = serializers.FileField(write_only=True, required=True)

    class Meta:
        model = KnowledgeDocument
        fields = (
            'id',
            'title',
            'file',
            'original_filename',
            'file_type',
            'file_size',
            'status',
            'uploaded_by',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'original_filename',
            'file_type',
            'file_size',
            'status',
            'uploaded_by',
            'created_at',
            'updated_at',
        )

    def validate_file(self, uploaded_file):
        max_size = (
            settings.RAG_CONFIG['MAX_DOCUMENT_SIZE_MB'] * 1024 * 1024
        )
        try:
            file_type = validate_upload(uploaded_file, max_size)
            extracted_text = extract_document_text(uploaded_file, file_type)
        except DocumentExtractionError as exc:
            raise serializers.ValidationError(exc.message) from exc
        uploaded_file.file_type = file_type
        uploaded_file.extracted_text = extracted_text
        return uploaded_file

    def create(self, validated_data):
        uploaded_file = validated_data.pop('file')
        file_type = uploaded_file.file_type
        extracted_text = getattr(uploaded_file, 'extracted_text', None)
        if extracted_text is None:
            extracted_text = extract_document_text(uploaded_file, file_type)
        stored_name = f'knowledge_base/{uuid.uuid4().hex}.{file_type.lower()}'
        uploaded_file.seek(0)
        stored_name = default_storage.save(stored_name, uploaded_file)
        try:
            uploaded_file.seek(0)
            sha256 = hashlib.sha256(uploaded_file.read()).hexdigest()
            return KnowledgeDocument.objects.create(
                **validated_data,
                original_filename=uploaded_file.name,
                stored_file=stored_name,
                file_type=file_type,
                file_size=uploaded_file.size,
                sha256=sha256,
                extracted_text=extracted_text,
                status=KnowledgeDocument.Status.PROCESSING,
            )
        except Exception:
            default_storage.delete(stored_name)
            raise


class DocumentChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentChunk
        fields = (
            'id',
            'document',
            'chunk_index',
            'text',
            'page_number',
            'character_count',
            'created_at',
        )
        read_only_fields = fields


class SimilaritySearchSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=2000, allow_blank=False)
    top_k = serializers.IntegerField(
        min_value=1,
        max_value=100,
        required=False,
    )
    min_similarity = serializers.FloatField(
        min_value=0,
        max_value=1,
        required=False,
    )
    document_id = serializers.IntegerField(min_value=1, required=False)
