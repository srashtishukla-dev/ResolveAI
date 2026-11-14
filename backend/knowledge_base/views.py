from django.core.files.storage import default_storage
from rest_framework import viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from knowledge_base.models import KnowledgeDocument
from knowledge_base.permissions import IsStaffForWrite
from knowledge_base.processing import DocumentProcessingError, process_document
from knowledge_base.embeddings import EmbeddingServiceError, embed_texts
from knowledge_base.search import SimilaritySearchError, search_similar_chunks
from knowledge_base.serializers import (
    DocumentChunkSerializer,
    KnowledgeDocumentSerializer,
    SimilaritySearchSerializer,
)


class KnowledgeDocumentViewSet(viewsets.ModelViewSet):
    queryset = KnowledgeDocument.objects.select_related('uploaded_by')
    serializer_class = KnowledgeDocumentSerializer
    permission_classes = (IsStaffForWrite,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    http_method_names = ('get', 'post', 'delete', 'head', 'options')

    def perform_destroy(self, instance):
        stored_name = instance.stored_file.name
        instance.delete()
        if stored_name:
            default_storage.delete(stored_name)

    def perform_create(self, serializer):
        document = serializer.save(uploaded_by=self.request.user)
        try:
            process_document(document)
        except DocumentProcessingError as exc:
            document.status = KnowledgeDocument.Status.FAILED
            document.error_message = str(exc)
            document.save(update_fields=('status', 'error_message', 'updated_at'))
            raise ValidationError({
                'detail': str(exc),
                'document_id': document.pk,
            }) from exc
        document.refresh_from_db()

    @action(
        detail=True,
        methods=('get',),
        permission_classes=(IsAuthenticated,),
        url_path='chunks',
    )
    def chunks(self, request, pk=None):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Only staff users can view document chunks.'},
                status=403,
            )
        document = self.get_object()
        serializer = DocumentChunkSerializer(
            document.chunks.all(),
            many=True,
        )
        return Response(serializer.data)

    @action(
        detail=False,
        methods=('post',),
        permission_classes=(IsAuthenticated,),
        url_path='search',
    )
    def search(self, request):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Only staff users can search document content.'},
                status=403,
            )
        serializer = SimilaritySearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            query_embedding = embed_texts([data['query']])[0]
            results = search_similar_chunks(
                query_embedding,
                top_k=data.get('top_k'),
                min_similarity=data.get('min_similarity'),
                document_id=data.get('document_id'),
            )
        except EmbeddingServiceError as exc:
            return Response(
                {'detail': str(exc)},
                status=503,
            )
        except SimilaritySearchError as exc:
            return Response(
                {'detail': str(exc)},
                status=503,
            )
        return Response({
            'count': len(results),
            'results': [
                {
                    'chunk_id': result.chunk_id,
                    'document_id': result.document_id,
                    'document_title': result.document_title,
                    'original_filename': result.original_filename,
                    'chunk_index': result.chunk_index,
                    'page_number': result.page_number,
                    'text': result.text,
                    'similarity': result.similarity,
                }
                for result in results
            ],
        })
