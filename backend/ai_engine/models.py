from django.conf import settings
from django.db import models


class Conversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_conversations',
    )
    title = models.CharField(max_length=150, default='New chat')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at',)
        indexes = [
            models.Index(fields=('user', 'updated_at')),
        ]

    def __str__(self):
        return f'{self.title} ({self.user})'


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant'

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    role = models.CharField(max_length=9, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at',)
        indexes = [
            models.Index(fields=('conversation', 'created_at')),
        ]

    def __str__(self):
        return f'{self.get_role_display()} message in conversation {self.conversation_id}'
