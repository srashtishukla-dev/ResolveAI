from django.db import connection
from django.db.utils import OperationalError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    try:
        connection.ensure_connection()
    except OperationalError:
        return Response({
            'application': 'ResolveAI',
            'status': 'unavailable',
        }, status=503)

    return Response({
        'application': 'ResolveAI',
        'status': 'healthy',
    })
