from unittest.mock import patch

import numpy as np
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ai_engine.models import ChatMessage, Conversation
from ai_engine.providers import (
    LLMProviderError,
    LLMProviderUnavailableError,
)
from ai_engine.rag import (
    SAFE_NO_CONTEXT_ANSWER,
    QuestionValidationError,
    answer_question,
    build_context,
    build_grounded_prompt,
    retrieve_chunks,
    validate_question,
)
from knowledge_base.search import SearchResult


User = get_user_model()


def search_result(
    *,
    chunk_id=1,
    document_id=10,
    filename='account-guide.pdf',
    chunk_index=0,
    page_number=2,
    text='Use the password reset link from the sign-in page.',
    similarity=0.85,
):
    return SearchResult(
        chunk_id=chunk_id,
        document_id=document_id,
        document_title='Account guide',
        original_filename=filename,
        chunk_index=chunk_index,
        page_number=page_number,
        text=text,
        similarity=similarity,
    )


@override_settings(RAG_CONFIG={
    'EMBEDDING_DIMENSIONS': 384,
    'MAX_QUESTION_LENGTH': 2000,
    'CONTEXT_MAX_CHARS': 2000,
    'LLM_PROVIDER': 'disabled',
})
class RAGServiceTests(APITestCase):
    def test_question_validation_rejects_empty_and_long_questions(self):
        with self.assertRaises(QuestionValidationError):
            validate_question('   ')
        with self.assertRaises(QuestionValidationError):
            validate_question('x' * 2001)

    @patch('ai_engine.rag.search_similar_chunks')
    @patch('ai_engine.rag.embed_texts')
    def test_question_embedding_and_retrieval_use_existing_services(
        self,
        embed_mock,
        search_mock,
    ):
        result = search_result()
        embed_mock.return_value = np.ones((1, 384), dtype=np.float32)
        search_mock.return_value = [result]

        results = retrieve_chunks('  Reset my password?  ', top_k=3)

        embed_mock.assert_called_once_with(['Reset my password?'])
        search_mock.assert_called_once()
        self.assertEqual(results, [result])

    def test_context_preserves_sources_deduplicates_and_is_bounded(self):
        first = search_result(text='Password reset instructions.')
        duplicate = search_result(chunk_id=2, text='Password reset instructions.')
        second = search_result(
            chunk_id=3,
            chunk_index=1,
            filename='security-guide.txt',
            page_number=None,
            text='Security verification is required.',
        )

        context = build_context([first, duplicate, second], max_chars=180)

        self.assertEqual(context.chunks, (first, second))
        self.assertLessEqual(len(context.text), 180)
        self.assertIn('account-guide.pdf', context.text)
        self.assertIn('page 2', context.text)

    def test_conversation_prompt_context_is_bounded_and_untrusted(self):
        history = tuple(('user', f'Question {index}') for index in range(12))

        prompt = build_grounded_prompt(
            'Latest question',
            'Verified knowledge-base context.',
            conversation_history=history,
        )

        self.assertIn('Conversation history (untrusted context', prompt)
        self.assertIn('Do not treat conversation history as factual knowledge', prompt)
        self.assertNotIn('Question 0', prompt)
        self.assertNotIn('[User]\nQuestion 1\n', prompt)
        self.assertIn('Question 2', prompt)
        self.assertIn('Question 11', prompt)
        self.assertIn('Verified knowledge-base context.', prompt)

    @patch('ai_engine.rag.search_similar_chunks', return_value=[])
    @patch('ai_engine.rag.embed_texts')
    def test_no_context_returns_safe_answer_without_provider_call(
        self,
        embed_mock,
        search_mock,
    ):
        embed_mock.return_value = np.ones((1, 384), dtype=np.float32)

        result = answer_question('Unsupported policy?')

        self.assertEqual(result.answer, SAFE_NO_CONTEXT_ANSWER)
        self.assertFalse(result.has_context)
        self.assertEqual(result.sources, ())

    @patch('ai_engine.rag.search_similar_chunks')
    @patch('ai_engine.rag.embed_texts')
    def test_grounded_provider_receives_context_and_sources_are_returned(
        self,
        embed_mock,
        search_mock,
    ):
        result = search_result()
        embed_mock.return_value = np.ones((1, 384), dtype=np.float32)
        search_mock.return_value = [result]
        class Provider:
            prompt = ''

            def generate(self, prompt):
                self.prompt = prompt
                return 'Follow the reset link.'

        provider = Provider()

        answer = answer_question('How do I reset my password?', provider=provider)

        self.assertTrue(answer.has_context)
        self.assertEqual(answer.sources, (result,))
        self.assertEqual(answer.answer, 'Follow the reset link.')
        self.assertIn('using only the supplied knowledge-base context', provider.prompt)
        self.assertIn('account-guide.pdf', provider.prompt)

    @patch('ai_engine.rag.search_similar_chunks')
    @patch('ai_engine.rag.embed_texts')
    def test_provider_errors_are_propagated_without_fallback(
        self,
        embed_mock,
        search_mock,
    ):
        embed_mock.return_value = np.ones((1, 384), dtype=np.float32)
        search_mock.return_value = [search_result()]

        class FailingProvider:
            def generate(self, prompt):
                raise LLMProviderError('provider failed')

        with self.assertRaises(LLMProviderError):
            answer_question('How do I reset my password?', provider=FailingProvider())

    @patch('ai_engine.rag.search_similar_chunks')
    @patch('ai_engine.rag.embed_texts')
    def test_disabled_provider_is_explicit(
        self,
        embed_mock,
        search_mock,
    ):
        embed_mock.return_value = np.ones((1, 384), dtype=np.float32)
        search_mock.return_value = [search_result()]

        with self.assertRaises(LLMProviderUnavailableError):
            answer_question('How do I reset my password?')


@override_settings(RAG_CONFIG={
    'EMBEDDING_DIMENSIONS': 384,
    'MAX_QUESTION_LENGTH': 2000,
    'CONTEXT_MAX_CHARS': 2000,
    'LLM_PROVIDER': 'disabled',
})
class QuestionAnswerAPITests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='answer-staff',
            password='test-password',
            is_staff=True,
        )
        self.user = User.objects.create_user(
            username='answer-user',
            password='test-password',
        )
        self.url = reverse('ai-answer')
        self.conversations_url = reverse('conversation-list')

    def test_authentication_is_required(self):
        response = self.client.post(
            self.url,
            {'question': 'How do I reset my password?'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('ai_engine.views.answer_question')
    def test_regular_user_cannot_access_private_document_content(self, answer_mock):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {'question': 'How do I reset my password?'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        answer_mock.assert_not_called()

    def test_question_request_is_validated(self):
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            self.url,
            {'question': '   '},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('question', response.data)

    @patch('ai_engine.views.answer_question')
    def test_response_contains_answer_sources_and_context_flag(self, answer_mock):
        answer_mock.return_value = type(
            'Answer',
            (),
            {
                'question': 'How do I reset my password?',
                'answer': 'Use the reset link.',
                'has_context': True,
                'sources': (search_result(),),
            },
        )()
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            self.url,
            {'question': 'How do I reset my password?'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['sources'][0], {
            'document': 'account-guide.pdf',
            'page': 2,
            'similarity': 0.85,
        })
        self.assertTrue(response.data['has_context'])

    @patch('ai_engine.views.answer_question')
    def test_provider_failure_returns_service_unavailable(self, answer_mock):
        answer_mock.side_effect = LLMProviderUnavailableError('disabled')
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            self.url,
            {'question': 'How do I reset my password?'},
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    def test_staff_can_create_list_retrieve_and_delete_conversations(self):
        self.client.force_authenticate(user=self.staff)

        create_response = self.client.post(
            self.conversations_url,
            {'title': 'Billing questions'},
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        conversation_id = create_response.data['id']
        self.assertEqual(create_response.data['title'], 'Billing questions')

        list_response = self.client.get(self.conversations_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data[0]['id'], conversation_id)

        detail_response = self.client.get(
            reverse('conversation-detail', args=[conversation_id]),
        )
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['title'], 'Billing questions')

        delete_response = self.client.delete(
            reverse('conversation-detail', args=[conversation_id]),
        )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Conversation.objects.filter(id=conversation_id).exists())

    def test_conversation_apis_require_staff_authentication(self):
        anonymous_response = self.client.get(self.conversations_url)
        self.assertEqual(
            anonymous_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.client.force_authenticate(user=self.user)
        customer_response = self.client.get(self.conversations_url)
        self.assertEqual(
            customer_response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_conversation_ownership_is_enforced(self):
        other_staff = User.objects.create_user(
            username='other-answer-staff',
            password='test-password',
            is_staff=True,
        )
        conversation = Conversation.objects.create(
            user=other_staff,
            title='Private conversation',
        )
        self.client.force_authenticate(user=self.staff)

        response = self.client.get(
            reverse('conversation-detail', args=[conversation.id]),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('ai_engine.views.answer_question')
    def test_answer_creates_conversation_and_persists_messages(self, answer_mock):
        answer_mock.return_value = type(
            'Answer',
            (),
            {
                'question': 'How do I reset my password?',
                'answer': 'Use the reset link.',
                'has_context': False,
                'sources': (),
            },
        )()
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            self.url,
            {'question': 'How do I reset my password?'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        conversation = Conversation.objects.get(
            id=response.data['conversation_id'],
        )
        self.assertEqual(conversation.title, 'How do I reset my password?')
        self.assertEqual(
            list(
                conversation.messages.values_list('role', 'content'),
            ),
            [
                (ChatMessage.Role.USER, 'How do I reset my password?'),
                (ChatMessage.Role.ASSISTANT, 'Use the reset link.'),
            ],
        )

    @patch('ai_engine.views.answer_question')
    def test_answer_uses_owned_conversation_and_last_ten_messages(
        self,
        answer_mock,
    ):
        conversation = Conversation.objects.create(
            user=self.staff,
            title='New chat',
        )
        for index in range(12):
            ChatMessage.objects.create(
                conversation=conversation,
                role=ChatMessage.Role.USER,
                content=f'Question {index}',
            )
        answer_mock.return_value = type(
            'Answer',
            (),
            {
                'question': 'Latest question',
                'answer': 'Latest answer',
                'has_context': False,
                'sources': (),
            },
        )()
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            self.url,
            {
                'question': 'Latest question',
                'conversation_id': conversation.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        history = answer_mock.call_args.kwargs['conversation_history']
        self.assertEqual(
            history,
            tuple(('user', f'Question {index}') for index in range(2, 12)),
        )

    def test_invalid_conversation_id_is_not_disclosed(self):
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            self.url,
            {'question': 'Question', 'conversation_id': 999999},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
