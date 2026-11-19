from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_engine.serializers import (
    ConversationSerializer,
    QuestionAnswerSerializer,
    TicketClassificationSerializer,
)
from ai_engine.models import Conversation, ChatMessage
from ai_engine.services import ModelNotTrainedError, classify_ticket
from ai_engine.rag import (
    ContextConstructionError,
    QuestionValidationError,
    answer_question,
)
from ai_engine.providers import LLMProviderError
from knowledge_base.embeddings import EmbeddingServiceError
from knowledge_base.search import SimilaritySearchError


class TicketClassificationView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = TicketClassificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            category, confidence = classify_ticket(**serializer.validated_data)
        except ModelNotTrainedError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({
            'predicted_category': category,
            'confidence': confidence,
        })


class ConversationListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    def _require_staff(self, request):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Only staff users can access conversations.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def get(self, request):
        denied = self._require_staff(request)
        if denied:
            return denied
        conversations = Conversation.objects.filter(
            user=request.user,
        ).prefetch_related('messages')
        serializer = ConversationSerializer(conversations, many=True)
        return Response(serializer.data)

    def post(self, request):
        denied = self._require_staff(request)
        if denied:
            return denied
        serializer = ConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = serializer.save(user=request.user)
        return Response(
            ConversationSerializer(conversation).data,
            status=status.HTTP_201_CREATED,
        )


class ConversationDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def _get_conversation(self, request, conversation_id):
        if not request.user.is_staff:
            return None
        return get_object_or_404(
            Conversation.objects.filter(user=request.user).prefetch_related('messages'),
            pk=conversation_id,
        )

    def get(self, request, conversation_id):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Only staff users can access conversations.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        conversation = self._get_conversation(request, conversation_id)
        return Response(ConversationSerializer(conversation).data)

    def delete(self, request, conversation_id):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Only staff users can access conversations.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        conversation = self._get_conversation(request, conversation_id)
        conversation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class QuestionAnswerView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Only staff users can query knowledge-base content.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = QuestionAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = None
        conversation_history = ()
        conversation_id = serializer.validated_data.get('conversation_id')
        if conversation_id is not None:
            conversation = get_object_or_404(
                Conversation.objects.filter(user=request.user),
                pk=conversation_id,
            )
            conversation_history = tuple(
                (
                    message.role,
                    message.content,
                )
                for message in list(
                    conversation.messages.order_by(
                        '-created_at',
                        '-id',
                    )[:10]
                )[::-1]
            )
        try:
            result = answer_question(
            serializer.validated_data['question'],
            uploaded_by=request.user,
            conversation_history=conversation_history,
         )
        except QuestionValidationError as exc:
            raise ValidationError({'question': str(exc)}) from exc
        except (EmbeddingServiceError, SimilaritySearchError, LLMProviderError):
            return Response(
                {'detail': 'The knowledge-base answer service is unavailable.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except ContextConstructionError:
            return Response(
                {'detail': 'The answer context could not be constructed.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if conversation is None:
            conversation = Conversation.objects.create(
                user=request.user,
                title=result.question[:150],
            )
        elif not conversation.messages.exists():
            conversation.title = result.question[:150]

        ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.Role.USER,
            content=result.question,
        )
        ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.Role.ASSISTANT,
            content=result.answer,
        )
        conversation.save(update_fields=('title', 'updated_at'))

        return Response({
            'conversation_id': conversation.id,
            'question': result.question,
            'answer': result.answer,
            'sources': [
                {
                    'document': source.original_filename,
                    'page': source.page_number,
                    'similarity': source.similarity,
                }
                for source in result.sources
            ],
            'has_context': result.has_context,
        })
