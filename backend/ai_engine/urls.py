from django.urls import path

from ai_engine.views import (
    ConversationDetailView,
    ConversationListCreateView,
    QuestionAnswerView,
    TicketClassificationView,
)

urlpatterns = [
    path('classify/', TicketClassificationView.as_view(), name='ticket-classify'),
    path('answer/', QuestionAnswerView.as_view(), name='ai-answer'),
    path(
        'conversations/',
        ConversationListCreateView.as_view(),
        name='conversation-list',
    ),
    path(
        'conversations/<int:conversation_id>/',
        ConversationDetailView.as_view(),
        name='conversation-detail',
    ),
]
