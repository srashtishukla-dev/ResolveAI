from rest_framework import serializers

from ai_engine.models import ChatMessage, Conversation


class TicketClassificationSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, allow_blank=False, trim_whitespace=True)
    description = serializers.CharField(allow_blank=False, trim_whitespace=True)


class QuestionAnswerSerializer(serializers.Serializer):
    question = serializers.CharField(
        max_length=2000,
        allow_blank=False,
        trim_whitespace=True,
    )
    conversation_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
    )


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ('id', 'role', 'content', 'created_at')
        read_only_fields = fields


class ConversationSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = ('id', 'title', 'created_at', 'updated_at', 'messages')
        read_only_fields = ('id', 'created_at', 'updated_at', 'messages')
