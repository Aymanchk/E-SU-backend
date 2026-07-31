from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    DashboardView,
    DocumentCategoryViewSet,
    DocumentCommentViewSet,
    DocumentFileViewSet,
    DocumentViewSet,
)

router = DefaultRouter()
router.register("document-categories", DocumentCategoryViewSet, basename="document-category")
router.register("documents", DocumentViewSet, basename="document")
router.register("document-files", DocumentFileViewSet, basename="document-file")
router.register("comments", DocumentCommentViewSet, basename="document-comment")

urlpatterns = [path("dashboard/", DashboardView.as_view(), name="dashboard")] + router.urls
