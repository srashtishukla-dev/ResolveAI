from django.db import models
from django.conf import settings


class Ticket(models.Model):
    class Category(models.TextChoices):
        TECHNICAL = 'TECHNICAL', 'Technical'
        BILLING = 'BILLING', 'Billing'
        ACCOUNT = 'ACCOUNT', 'Account'
        GENERAL = 'GENERAL', 'General'

    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        URGENT = 'URGENT', 'Urgent'

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_PROGRESS = 'IN_PROGRESS', 'In progress'
        RESOLVED = 'RESOLVED', 'Resolved'
        CLOSED = 'CLOSED', 'Closed'

    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.GENERAL,
        db_index=True,
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_tickets',
        editable=False,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('created_by', 'created_at')),
        ]

    def __str__(self):
        return self.title
