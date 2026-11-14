from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ai_engine import services
from ai_engine.evaluation import evaluate_classifier
from ai_engine.ml_data import TRAINING_EXAMPLES, TRAINING_LABELS
from ai_engine.services import train_classifier


User = get_user_model()


class TicketClassificationAPITests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.model_directory = TemporaryDirectory()
        cls.model_path = Path(cls.model_directory.name) / 'classifier.joblib'
        cls.original_model_path = services.MODEL_PATH
        services.MODEL_PATH = cls.model_path
        train_classifier(cls.model_path)

    @classmethod
    def tearDownClass(cls):
        services.MODEL_PATH = cls.original_model_path
        services.load_classifier.cache_clear()
        cls.model_directory.cleanup()
        super().tearDownClass()

    def setUp(self):
        services.MODEL_PATH = self.model_path
        services.load_classifier.cache_clear()
        self.user = User.objects.create_user(
            username='classifier-user',
            password='test-password',
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse('ticket-classify')

    def test_valid_classification_request(self):
        response = self.client.post(self.url, {
            'title': 'Payment failed',
            'description': 'Money was deducted but my order is still pending',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['predicted_category'], 'BILLING')

    def test_missing_title_is_rejected(self):
        response = self.client.post(self.url, {
            'description': 'The application crashes when I open it.',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title', response.data)

    def test_missing_description_is_rejected(self):
        response = self.client.post(self.url, {
            'title': 'Payment failed',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('description', response.data)

    def test_unauthenticated_access_is_rejected(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(self.url, {
            'title': 'Payment failed',
            'description': 'The payment did not complete.',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_confidence_is_between_zero_and_one(self):
        response = self.client.post(self.url, {
            'title': 'Account locked',
            'description': 'Too many sign-in attempts locked my profile.',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['confidence'], 0)
        self.assertLessEqual(response.data['confidence'], 1)

    def test_missing_model_artifact_returns_service_unavailable(self):
        missing_path = self.model_path.with_name('missing.joblib')
        services.MODEL_PATH = missing_path
        services.load_classifier.cache_clear()

        response = self.client.post(self.url, {
            'title': 'Payment failed',
            'description': 'The payment did not complete.',
        }, format='json')

        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        self.assertIn('not been trained', response.data['detail'])


class ClassifierEvaluationTests(APITestCase):
    def test_dataset_is_balanced_and_has_no_duplicate_rows(self):
        self.assertEqual(len(TRAINING_EXAMPLES), 120)
        self.assertEqual(len(TRAINING_LABELS), len(TRAINING_EXAMPLES))
        texts = [f'{title}. {description}' for title, description in TRAINING_EXAMPLES]
        self.assertEqual(len(texts), len(set(texts)))

    def test_stratified_evaluation_reports_all_categories(self):
        metrics = evaluate_classifier()

        self.assertEqual(metrics['class_counts'], {
            'TECHNICAL': 30,
            'BILLING': 30,
            'ACCOUNT': 30,
            'GENERAL': 30,
        })
        self.assertEqual(metrics['duplicate_count'], 0)
        self.assertEqual(metrics['train_test_overlap_count'], 0)
        self.assertEqual(set(metrics['per_class']), {
            'TECHNICAL',
            'BILLING',
            'ACCOUNT',
            'GENERAL',
        })
        self.assertEqual(len(metrics['confusion_matrix']), 4)
