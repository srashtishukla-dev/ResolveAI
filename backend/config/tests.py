
from unittest.mock import patch

from django.conf import settings
from django.db.utils import OperationalError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


class HealthCheckTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_django_email_settings_use_standard_configuration(self):
        self.assertTrue(settings.EMAIL_BACKEND)
        self.assertEqual(settings.EMAIL_PORT, 587)

    def test_health_check_returns_healthy_status(self):
        response = self.client.get('/api/health/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                'application': 'ResolveAI',
                'status': 'healthy',
            },
        )

    @patch('config.views.connection.ensure_connection')
    def test_health_check_reports_database_outage(self, ensure_connection):
        ensure_connection.side_effect = OperationalError(
            'database unavailable'
        )

        response = self.client.get('/api/health/')

        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        self.assertEqual(
            response.json(),
            {
                'application': 'ResolveAI',
                'status': 'unavailable',
            },
        )
