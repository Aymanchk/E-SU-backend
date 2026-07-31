from rest_framework.routers import DefaultRouter

from .views import DocumentCategoryViewSet

router = DefaultRouter()
router.register("document-categories", DocumentCategoryViewSet, basename="document-category")

urlpatterns = router.urls
