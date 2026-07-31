from django.contrib import admin

from .models import Document, DocumentCategory


@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "status", "retention_period_days", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "code")
    filter_horizontal = ("allowed_departments",)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "registration_number", "status", "priority", "author", "created_at")
    list_filter = ("status", "priority", "document_type", "category")
    search_fields = ("title", "registration_number", "description")
    autocomplete_fields = ("author", "responsible", "department", "category")
