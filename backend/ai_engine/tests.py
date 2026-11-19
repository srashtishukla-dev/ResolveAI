from pathlib import Path
from ai_engine.serializers import QuestionAnswerSerializer
from ai_engine.models import Conversation
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

class ConversationSecurityTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staff-security',
            password='test-password',
            is_staff=True,
        )
        self.other_staff = User.objects.create_user(
            username='other-staff-security',
            password='test-password',
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            username='customer-security',
            password='test-password',
        )

        self.conversation = Conversation.objects.create(
            user=self.staff,
            title='Staff conversation',
        )
        self.other_conversation = Conversation.objects.create(
            user=self.other_staff,
            title='Other staff conversation',
        )

    def test_customer_cannot_list_conversations(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(reverse('conversation-list'))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_customer_cannot_create_conversation(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            reverse('conversation-list'),
            {'title': 'Unauthorized conversation'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_customer_cannot_access_conversation_detail(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(
            reverse(
                'conversation-detail',
                kwargs={'conversation_id': self.conversation.id},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_customer_cannot_delete_conversation(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.delete(
            reverse(
                'conversation-detail',
                kwargs={'conversation_id': self.conversation.id},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            Conversation.objects.filter(pk=self.conversation.pk).exists()
        )

    def test_staff_can_only_list_own_conversations(self):
        self.client.force_authenticate(user=self.staff)

        response = self.client.get(reverse('conversation-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = [item['id'] for item in response.data]
        self.assertIn(self.conversation.id, returned_ids)
        self.assertNotIn(self.other_conversation.id, returned_ids)

    def test_staff_cannot_view_another_staff_conversation(self):
        self.client.force_authenticate(user=self.staff)

        response = self.client.get(
            reverse(
                'conversation-detail',
                kwargs={'conversation_id': self.other_conversation.id},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_staff_cannot_delete_another_staff_conversation(self):
        self.client.force_authenticate(user=self.staff)

        response = self.client.delete(
            reverse(
                'conversation-detail',
                kwargs={'conversation_id': self.other_conversation.id},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(
            Conversation.objects.filter(pk=self.other_conversation.pk).exists()
        )

class QuestionAnswerSerializerTests(APITestCase):
    def test_valid_question_is_accepted(self):
        serializer = QuestionAnswerSerializer(data={
            'question': 'How do I reset my password?',
        })

        self.assertTrue(serializer.is_valid())

    def test_whitespace_only_question_is_rejected(self):
        serializer = QuestionAnswerSerializer(data={
            'question': '     ',
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('question', serializer.errors)

    def test_question_over_2000_characters_is_rejected(self):
        serializer = QuestionAnswerSerializer(data={
            'question': 'a' * 2001,
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('question', serializer.errors)

    def test_zero_conversation_id_is_rejected(self):
        serializer = QuestionAnswerSerializer(data={
            'question': 'How do I reset my password?',
            'conversation_id': 0,
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('conversation_id', serializer.errors)

    def test_null_conversation_id_is_accepted(self):
        serializer = QuestionAnswerSerializer(data={
            'question': 'How do I reset my password?',
            'conversation_id': None,
        })

        self.assertTrue(serializer.is_valid())

class QuestionAnswerAccessTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='answer-staff',
            password='test-password',
            is_staff=True,
        )
        self.other_staff = User.objects.create_user(
            username='answer-other-staff',
            password='test-password',
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            username='answer-customer',
            password='test-password',
        )
        self.other_conversation = Conversation.objects.create(
            user=self.other_staff,
            title='Private conversation',
        )
        self.url = reverse('ai-answer')

    def test_customer_cannot_submit_ai_question(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            self.url,
            {'question': 'How do I reset my password?'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_cannot_use_another_staff_conversation(self):
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            self.url,
            {
                'question': 'How do I reset my password?',
                'conversation_id': self.other_conversation.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
class ClassifierInputValidationTests(APITestCase):
    def test_empty_title_is_rejected(self):
        from ai_engine.services import classify_ticket

        with self.assertRaises(ValueError):
            classify_ticket('   ', 'Cannot log in')

    def test_empty_description_is_rejected(self):
        from ai_engine.services import classify_ticket

        with self.assertRaises(ValueError):
            classify_ticket('Login issue', '   ')        
class ClassifierPredictionTests(APITestCase):
    def test_returns_category_with_highest_confidence(self):
        from unittest.mock import Mock, patch
        import numpy as np
        from ai_engine.services import classify_ticket

        classifier = Mock()
        classifier.classes_ = ['BILLING', 'TECHNICAL', 'GENERAL']
        classifier.predict_proba.return_value = np.array(
            [[0.2, 0.7, 0.1]]
        )

        with patch(
            'ai_engine.services.load_classifier',
            return_value=classifier
        ):
            result = classify_ticket('Login issue', 'Unable to log in')

        self.assertEqual(result, ('TECHNICAL', 0.7))
        classifier.predict_proba.assert_called_once()
    def test_strips_title_and_description_before_prediction(self):
        from unittest.mock import Mock, patch
        import numpy as np
        from ai_engine.services import classify_ticket

        classifier = Mock()
        classifier.classes_ = ['TECHNICAL']
        classifier.predict_proba.return_value = np.array([[1.0]])

        with patch(
            'ai_engine.services.load_classifier',
            return_value=classifier
        ):
            classify_ticket('  Login issue  ', '  Unable to log in  ')

        classifier.predict_proba.assert_called_once_with(
            ['Login issue. Unable to log in']
        )    