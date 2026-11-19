from rest_framework import serializers

from tickets.models import Ticket


class TicketSerializer(serializers.ModelSerializer):
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Ticket
        fields = (
            'id',
            'title',
            'description',
            'category',
            'priority',
            'status',
            'created_by',
            'assigned_to',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_by', 'created_at', 'updated_at')

    def validate_assigned_to(self, assigned_to):
        request = self.context.get('request')
        if request and not request.user.is_staff and assigned_to not in (None, request.user):
            raise serializers.ValidationError(
                'You can only assign a ticket to yourself.'
            )
        return assigned_to

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Title cannot be blank.')
        return value

    def validate_description(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Description cannot be blank.')
        return value
