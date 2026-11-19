from rest_framework import permissions, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination

from tickets.models import Ticket
from tickets.serializers import TicketSerializer


class TicketPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class TicketViewSet(viewsets.ModelViewSet):
    serializer_class = TicketSerializer
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = TicketPagination

    def get_queryset(self):
        queryset = Ticket.objects.select_related('created_by', 'assigned_to')
        if not self.request.user.is_staff:
            queryset = queryset.filter(created_by=self.request.user)

        for field in ('status', 'priority', 'category'):
            value = self.request.query_params.get(field)
            if value:
                valid_values = {
                    choice_value
                    for choice_value, _ in Ticket._meta.get_field(field).choices
                }
                if value not in valid_values:
                    raise ValidationError({
                        field: f'Unsupported {field} filter.',
                    })
                queryset = queryset.filter(**{field: value})
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
