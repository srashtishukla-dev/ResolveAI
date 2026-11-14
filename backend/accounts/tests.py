from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


User = get_user_model()


class CustomerRegistrationAPITests(APITestCase):
    def setUp(self):
        self.url = reverse('customer-register')
        self.valid_payload = {
            'name': 'Ada Lovelace',
            'email': 'ada@example.com',
            'username': 'ada',
            'password': 'A-strong-password-123!',
            'password_confirmation': 'A-strong-password-123!',
        }

    def test_customer_can_register_with_hashed_password(self):
        response = self.client.post(self.url, self.valid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username='ada')
        self.assertEqual(user.first_name, 'Ada Lovelace')
        self.assertEqual(user.email, 'ada@example.com')
        self.assertTrue(user.check_password(self.valid_payload['password']))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertNotEqual(user.password, self.valid_payload['password'])

    def test_duplicate_username_is_rejected(self):
        User.objects.create_user(username='ada', password='Existing-password-123!')

        response = self.client.post(self.url, self.valid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)

    def test_duplicate_email_is_rejected_case_insensitively(self):
        User.objects.create_user(
            username='existing',
            email='ADA@EXAMPLE.COM',
            password='Existing-password-123!',
        )

        response = self.client.post(self.url, self.valid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_invalid_password_is_rejected(self):
        payload = {
            **self.valid_payload,
            'password': 'password',
            'password_confirmation': 'password',
        }

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)

    def test_invalid_email_is_rejected(self):
        response = self.client.post(
            self.url,
            {**self.valid_payload, 'email': 'not-an-email'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_password_confirmation_mismatch_is_rejected(self):
        response = self.client.post(
            self.url,
            {**self.valid_payload, 'password_confirmation': 'Different-password-123!'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password_confirmation', response.data)

    def test_missing_required_fields_are_rejected(self):
        response = self.client.post(self.url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            set(response.data),
            {'name', 'email', 'username', 'password', 'password_confirmation'},
        )

    def test_registration_cannot_escalate_privileges(self):
        response = self.client.post(
            self.url,
            {
                **self.valid_payload,
                'username': 'attempted-admin',
                'is_staff': True,
                'is_superuser': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username='attempted-admin')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_registered_customer_can_obtain_jwt_tokens(self):
        self.client.post(self.url, self.valid_payload, format='json')

        response = self.client.post(
            '/api/token/',
            {
                'username': self.valid_payload['username'],
                'password': self.valid_payload['password'],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_registered_customer_is_forbidden_from_ai_endpoint(self):
        customer = User.objects.create_user(
            username='customer',
            password='Customer-password-123!',
        )
        self.client.force_authenticate(user=customer)

        response = self.client.post(
            '/api/ai/answer/',
            {'question': 'How do I reset my password?'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_registered_customer_is_forbidden_from_knowledge_base(self):
        customer = User.objects.create_user(
            username='customer',
            password='Customer-password-123!',
        )
        self.client.force_authenticate(user=customer)

        response = self.client.get('/api/knowledge-base/documents/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_user_is_unauthorized_for_ai_endpoint(self):
        response = self.client.post(
            '/api/ai/answer/',
            {'question': 'How do I reset my password?'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('ai_engine.views.answer_question')
    def test_staff_user_retains_ai_access(self, answer_question):
        staff = User.objects.create_user(
            username='staff',
            password='Staff-password-123!',
            is_staff=True,
        )
        answer_question.return_value = SimpleNamespace(
            question='How do I reset my password?',
            answer='Use the password reset link.',
            sources=(),
            has_context=False,
        )
        self.client.force_authenticate(user=staff)

        response = self.client.post(
            '/api/ai/answer/',
            {'question': 'How do I reset my password?'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_staff_user_retains_knowledge_base_access(self):
        staff = User.objects.create_user(
            username='staff',
            password='Staff-password-123!',
            is_staff=True,
        )
        self.client.force_authenticate(user=staff)

        response = self.client.get('/api/knowledge-base/documents/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_current_user_request_is_rejected(self):
        response = self.client.get(reverse('current-user'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_current_user_profile_contains_only_safe_fields(self):
        customer = User.objects.create_user(
            username='profile-customer',
            password='Customer-password-123!',
        )
        self.client.force_authenticate(user=customer)

        response = self.client.get(reverse('current-user'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data),
            {'id', 'username', 'is_staff'},
        )
        self.assertEqual(response.data['id'], customer.id)
        self.assertEqual(response.data['username'], 'profile-customer')
        self.assertFalse(response.data['is_staff'])

    def test_staff_current_user_profile_reports_staff_status(self):
        staff = User.objects.create_user(
            username='profile-staff',
            password='Staff-password-123!',
            is_staff=True,
        )
        self.client.force_authenticate(user=staff)

        response = self.client.get(reverse('current-user'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data),
            {'id', 'username', 'is_staff'},
        )
        self.assertTrue(response.data['is_staff'])
