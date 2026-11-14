from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import CustomerRegistrationSerializer


class CustomerRegistrationView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = CustomerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                'detail': 'Customer account created successfully.',
                'username': user.username,
            },
            status=status.HTTP_201_CREATED,
        )


class CurrentUserView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response({
            'id': request.user.id,
            'username': request.user.username,
            'is_staff': request.user.is_staff,
        })
