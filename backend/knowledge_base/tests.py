from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from pypdf import PdfWriter
from rest_framework import status
from rest_framework.test import APITestCase

from knowledge_base.chunking import chunk_text
from knowledge_base.embeddings import (
    EmbeddingServiceError,
    embed_texts,
    load_embedding_model,
)
from knowledge_base.models import KnowledgeDocument
from knowledge_base.processing import DocumentProcessingError, process_document
from knowledge_base.search import SimilaritySearchError, search_similar_chunks
from knowledge_base.services import extract_document_text


User = get_user_model()


def pdf_bytes():
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(output)
    return output.getvalue()


@override_settings(RAG_CONFIG={
    'MAX_DOCUMENT_SIZE_MB': 10,
    'CHUNK_SIZE': 2000,
    'CHUNK_OVERLAP': 200,
    'EMBEDDING_MODEL': 'test-embedding-model',
    'EMBEDDING_DIMENSIONS': 384,
    'EMBEDDING_BATCH_SIZE': 32,
})
class KnowledgeDocumentAPITests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_directory = TemporaryDirectory()
        cls.override_media = override_settings(
            MEDIA_ROOT=Path(cls.media_directory.name)
        )
        cls.override_media.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override_media.disable()
        cls.media_directory.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.embedding_patcher = patch(
            'knowledge_base.processing.embed_texts',
            side_effect=lambda texts: np.ones(
                (len(texts), 384),
                dtype=np.float32,
            ),
        )
        self.embedding_patcher.start()
        self.addCleanup(self.embedding_patcher.stop)
        self.staff = User.objects.create_user(
            username='kb-staff',
            password='test-password',
            is_staff=True,
        )
        self.user = User.objects.create_user(
            username='kb-user',
            password='test-password',
        )
        self.url = reverse('knowledge-document-list')

    def upload(self, user, filename='guide.txt', content=b'Billing details'):
        self.client.force_authenticate(user=user)
        return self.client.post(
            self.url,
            {
                'title': 'Support guide',
                'file': SimpleUploadedFile(
                    filename,
                    content,
                    content_type='text/plain',
                ),
            },
            format='multipart',
        )

    @patch('knowledge_base.services.PdfReader')
    def test_staff_can_upload_pdf(self, reader_class):
        reader_class.return_value.pages = [
            type('Page', (), {'extract_text': lambda self: 'PDF support text'})()
        ]

        response = self.upload(
            self.staff,
            'guide.pdf',
            b'%PDF-1.7 synthetic test content',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        document = KnowledgeDocument.objects.get()
        self.assertEqual(document.file_type, 'PDF')
        self.assertEqual(document.extracted_text, 'PDF support text')
        self.assertEqual(document.status, KnowledgeDocument.Status.PROCESSED)
        chunk = document.chunks.get()
        self.assertEqual(chunk.page_number, 1)
        self.assertEqual(chunk.character_count, len(chunk.text))
        self.assertTrue(document.stored_file.name.startswith('knowledge_base/'))
        self.assertNotEqual(document.stored_file.name, 'guide.pdf')

    def test_staff_can_upload_txt(self):
        response = self.upload(self.staff)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        document = KnowledgeDocument.objects.get()
        self.assertEqual(document.file_type, 'TXT')
        self.assertEqual(document.extracted_text, 'Billing details')
        self.assertIsNone(document.chunks.get().page_number)

    def test_invalid_extension_is_rejected(self):
        response = self.upload(self.staff, 'guide.docx', b'text')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(KnowledgeDocument.objects.count(), 0)

    def test_empty_file_is_rejected(self):
        response = self.upload(self.staff, 'empty.txt', b'')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_oversized_file_is_rejected(self):
        with override_settings(RAG_CONFIG={'MAX_DOCUMENT_SIZE_MB': 1}):
            response = self.upload(
                self.staff,
                'large.txt',
                b'x' * (1024 * 1024 + 1),
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_corrupted_pdf_is_rejected(self):
        response = self.upload(
            self.staff,
            'broken.pdf',
            b'%PDF-1.7 not a valid PDF',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_regular_user_cannot_upload(self):
        response = self.upload(self.user)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_user_cannot_list_documents(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_regular_user_cannot_list_documents(self):
        self.upload(self.staff)
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_cannot_retrieve_documents(self):
        self.upload(self.staff)
        document = KnowledgeDocument.objects.get()
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse('knowledge-document-detail', args=[document.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_user_cannot_retrieve_documents(self):
        self.upload(self.staff)
        document = KnowledgeDocument.objects.get()
        self.client.force_authenticate(user=None)

        response = self.client.get(
            reverse('knowledge-document-detail', args=[document.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_staff_can_list_and_retrieve_documents(self):
        self.upload(self.staff)
        document = KnowledgeDocument.objects.get()
        self.client.force_authenticate(user=self.staff)

        list_response = self.client.get(self.url)
        detail_response = self.client.get(
            reverse('knowledge-document-detail', args=[document.pk])
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertNotIn('extracted_text', detail_response.data)

    def test_regular_user_cannot_delete(self):
        self.upload(self.staff)
        document = KnowledgeDocument.objects.get()
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(
            reverse('knowledge-document-detail', args=[document.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_delete_and_file_is_cleaned_up(self):
        self.upload(self.staff)
        document = KnowledgeDocument.objects.get()
        stored_path = Path(document.stored_file.path)
        self.client.force_authenticate(user=self.staff)

        response = self.client.delete(
            reverse('knowledge-document-detail', args=[document.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(KnowledgeDocument.objects.filter(pk=document.pk).exists())
        self.assertFalse(stored_path.exists())

    def test_staff_can_list_chunks_but_regular_users_cannot(self):
        self.upload(self.staff)
        document = KnowledgeDocument.objects.get()
        chunk_url = reverse(
            'knowledge-document-chunks',
            args=[document.pk],
        )

        self.client.force_authenticate(user=self.staff)
        staff_response = self.client.get(chunk_url)
        self.client.force_authenticate(user=self.user)
        user_response = self.client.get(chunk_url)

        self.assertEqual(staff_response.status_code, status.HTTP_200_OK)
        self.assertEqual(user_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(staff_response.data[0]['chunk_index'], 0)

    def test_reprocessing_replaces_chunks_without_duplicates(self):
        response = self.upload(self.staff, content=b'First paragraph. ' * 200)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        document = KnowledgeDocument.objects.get()
        first_ids = list(document.chunks.values_list('id', flat=True))

        process_document(document)

        self.assertEqual(document.chunks.count(), len(first_ids))
        self.assertEqual(
            list(document.chunks.values_list('chunk_index', flat=True)),
            list(range(document.chunks.count())),
        )
        self.assertTrue(
            set(document.chunks.values_list('id', flat=True)).isdisjoint(first_ids)
        )

    @patch('knowledge_base.views.process_document')
    def test_processing_failure_marks_document_failed(self, process_mock):
        process_mock.side_effect = DocumentProcessingError('processing failed')

        response = self.upload(self.staff)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        document = KnowledgeDocument.objects.get()
        self.assertEqual(document.status, KnowledgeDocument.Status.FAILED)
        self.assertEqual(document.chunks.count(), 0)


class EmbeddingServiceTests(APITestCase):
    def test_batch_embedding_has_expected_shape_and_finite_values(self):
        fake_model = type(
            'FakeModel',
            (),
            {
                'encode': lambda self, texts, **kwargs: np.ones(
                    (len(texts), 384),
                    dtype=np.float32,
                )
            },
        )()
        with patch(
            'knowledge_base.embeddings.load_embedding_model',
            return_value=fake_model,
        ):
            vectors = embed_texts(['first chunk', 'second chunk'])

        self.assertEqual(vectors.shape, (2, 384))
        self.assertEqual(vectors.dtype, np.float32)
        self.assertTrue(np.isfinite(vectors).all())

    def test_empty_batch_returns_empty_matrix(self):
        vectors = embed_texts([])

        self.assertEqual(vectors.shape, (0, 384))

    def test_empty_text_is_rejected(self):
        with self.assertRaises(EmbeddingServiceError):
            embed_texts([''])

    def test_invalid_model_output_is_rejected(self):
        fake_model = type(
            'FakeModel',
            (),
            {
                'encode': lambda self, texts, **kwargs: np.ones(
                    (len(texts), 3),
                    dtype=np.float32,
                )
            },
        )()
        with patch(
            'knowledge_base.embeddings.load_embedding_model',
            return_value=fake_model,
        ):
            with self.assertRaises(EmbeddingServiceError):
                embed_texts(['chunk'])

    def test_model_loading_failure_is_wrapped(self):
        load_embedding_model.cache_clear()
        def unavailable_model(_model_name):
            raise RuntimeError('unavailable')

        module = type(
            'Module',
            (),
            {'SentenceTransformer': staticmethod(unavailable_model)},
        )()
        with patch.dict(
            'sys.modules',
            {'sentence_transformers': module},
        ):
            with self.assertRaises(EmbeddingServiceError):
                load_embedding_model()
        load_embedding_model.cache_clear()


class SimilaritySearchTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username='search-staff',
            password='test-password',
            is_staff=True,
        )
        cls.user = User.objects.create_user(
            username='search-user',
            password='test-password',
        )
        cls.account_document = KnowledgeDocument.objects.create(
            uploaded_by=cls.staff,
            title='Account guide',
            original_filename='account.txt',
            file_type='TXT',
            file_size=10,
            sha256='a' * 64,
            status=KnowledgeDocument.Status.PROCESSED,
        )
        cls.billing_document = KnowledgeDocument.objects.create(
            uploaded_by=cls.staff,
            title='Billing guide',
            original_filename='billing.txt',
            file_type='TXT',
            file_size=10,
            sha256='b' * 64,
            status=KnowledgeDocument.Status.PROCESSED,
        )
        cls.account_chunk = cls.account_document.chunks.create(
            chunk_index=0,
            text='Account login and password reset instructions.',
            character_count=46,
            embedding=[1.0] + [0.0] * 383,
            embedding_model='test',
            embedding_dimension=384,
        )
        cls.billing_chunk = cls.billing_document.chunks.create(
            chunk_index=0,
            text='Billing payment and duplicate charge instructions.',
            character_count=49,
            embedding=[0.0, 1.0] + [0.0] * 382,
            embedding_model='test',
            embedding_dimension=384,
        )

    def test_numpy_search_ranks_relevant_chunk_first(self):
        results = search_similar_chunks(
            np.array([1.0] + [0.0] * 383, dtype=np.float32),
            top_k=2,
        )

        self.assertEqual([result.chunk_id for result in results], [
            self.account_chunk.pk,
            self.billing_chunk.pk,
        ])
        self.assertEqual(results[0].similarity, 1.0)

    def test_top_k_and_threshold_are_applied(self):
        results = search_similar_chunks(
            np.array([1.0] + [0.0] * 383, dtype=np.float32),
            top_k=1,
            min_similarity=0.9,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].document_id, self.account_document.pk)

    def test_document_filter_is_applied(self):
        results = search_similar_chunks(
            np.array([1.0] + [0.0] * 383, dtype=np.float32),
            document_id=self.billing_document.pk,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].document_id, self.billing_document.pk)

    def test_invalid_query_embedding_is_rejected(self):
        with self.assertRaises(SimilaritySearchError):
            search_similar_chunks(np.zeros(384, dtype=np.float32))

    @patch('knowledge_base.views.embed_texts')
    def test_staff_search_api_returns_ranked_results(self, embed_mock):
        embed_mock.return_value = np.array(
            [[1.0] + [0.0] * 383],
            dtype=np.float32,
        )
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            reverse('knowledge-document-search'),
            {'query': 'How do I log in?', 'top_k': 1},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(
            response.data['results'][0]['document_id'],
            self.account_document.pk,
        )

    def test_regular_user_cannot_search_document_content(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse('knowledge-document-search'),
            {'query': 'How do I log in?'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_search_api_validates_empty_query(self):
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            reverse('knowledge-document-search'),
            {'query': ''},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class DocumentExtractionTests(APITestCase):
    def test_txt_extraction_supports_utf8_bom(self):
        uploaded_file = SimpleUploadedFile(
            'guide.txt',
            '\ufeffSupport policy'.encode('utf-8'),
        )

        self.assertEqual(
            extract_document_text(uploaded_file, 'TXT'),
            'Support policy',
        )


class TextChunkingTests(APITestCase):
    def test_empty_and_whitespace_text_returns_no_chunks(self):
        self.assertEqual(chunk_text(''), [])
        self.assertEqual(chunk_text(' \n\t '), [])

    def test_short_text_returns_one_chunk(self):
        text = 'A short support paragraph.'

        self.assertEqual(chunk_text(text, chunk_size=100, overlap=10), [text])

    def test_long_text_has_ordered_overlap_without_duplicates(self):
        sentences = [f'Sentence {index} explains the support process.' for index in range(20)]
        text = ' '.join(sentences)

        chunks = chunk_text(text, chunk_size=120, overlap=30)

        self.assertGreater(len(chunks), 1)
        self.assertEqual(len(chunks), len(set(chunks)))
        for index in range(1, len(chunks)):
            self.assertTrue(
                set(chunks[index].split()) & set(chunks[index - 1].split())
            )

    def test_chunking_does_not_split_words_at_boundaries(self):
        chunks = chunk_text(
            'Alpha support information. Beta billing information.',
            chunk_size=30,
            overlap=5,
        )

        self.assertTrue(all(not chunk.startswith(' ') for chunk in chunks))
        self.assertTrue(all(not chunk.endswith(' ') for chunk in chunks))


# Create your tests here.
