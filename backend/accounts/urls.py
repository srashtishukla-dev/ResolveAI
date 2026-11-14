from django.urls import path

from accounts.views import CustomerRegistrationView, CurrentUserView


urlpatterns = [
    path('register/', CustomerRegistrationView.as_view(), name='customer-register'),
    path('me/', CurrentUserView.as_view(), name='current-user'),
]
