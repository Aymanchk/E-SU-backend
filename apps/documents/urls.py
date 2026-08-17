from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ApprovalRouteTemplateViewSet,
    DashboardView,
    DocumentCategoryViewSet,
    DocumentCommentViewSet,
    DocumentFileViewSet,
    DocumentViewSet,
)

router = DefaultRouter()
router.register(
    "approval-route-templates",
    ApprovalRouteTemplateViewSet,
    basename="approval-route-template",
)
router.register("document-categories", DocumentCategoryViewSet, basename="document-category")
router.register("documents", DocumentViewSet, basename="document")
router.register("document-files", DocumentFileViewSet, basename="document-file")
router.register("comments", DocumentCommentViewSet, basename="document-comment")

urlpatterns = [path("dashboard/", DashboardView.as_view(), name="dashboard")] + router.urls
