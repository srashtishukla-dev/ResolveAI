from rest_framework.routers import DefaultRouter

from knowledge_base.views import KnowledgeDocumentViewSet

router = DefaultRouter()
router.register(
    'knowledge-base/documents',
    KnowledgeDocumentViewSet,
    basename='knowledge-document',
)

urlpatterns = router.urls
