from django.contrib import admin

from .models import DocumentCategory


@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "status", "retention_period_days", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "code")
    filter_horizontal = ("allowed_departments",)
