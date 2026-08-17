from django.contrib import admin

from .models import (
    ApprovalAction,
    ApprovalRoute,
    ApprovalRouteTemplate,
    ApprovalRouteTemplateStep,
    ApprovalStep,
    Document,
    DocumentCategory,
    DocumentComment,
    DocumentFile,
    DocumentHistory,
    DocumentNumberCounter,
)


@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "status", "retention_period_days", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "code")
    filter_horizontal = ("allowed_departments",)


class ApprovalRouteTemplateStepInline(admin.TabularInline):
    model = ApprovalRouteTemplateStep
    extra = 0


@admin.register(ApprovalRouteTemplate)
class ApprovalRouteTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active", "created_at")
    list_filter = ("is_active", "category")
    search_fields = ("name", "category__name", "category__code")
    inlines = (ApprovalRouteTemplateStepInline,)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "registration_number", "status", "priority", "author", "created_at")
    list_filter = ("status", "priority", "document_type", "category")
    search_fields = ("title", "registration_number", "description")
    autocomplete_fields = ("author", "responsible", "department", "category")


@admin.register(DocumentNumberCounter)
class DocumentNumberCounterAdmin(admin.ModelAdmin):
    list_display = ("department", "year", "last_number", "updated_at")
    list_filter = ("year",)
    search_fields = ("department__name", "department__code")
    readonly_fields = (
        "department",
        "category",
        "year",
        "last_number",
        "updated_at",
    )


@admin.register(DocumentFile)
class DocumentFileAdmin(admin.ModelAdmin):
    list_display = ("original_name", "document", "file_type", "size", "is_main", "created_at")
    list_filter = ("file_type", "is_main")
    search_fields = ("original_name", "document__title", "document__registration_number")
    readonly_fields = (
        "document",
        "file",
        "original_name",
        "file_type",
        "mime_type",
        "size",
        "is_main",
        "uploaded_by",
        "created_at",
    )


class ApprovalStepInline(admin.TabularInline):
    model = ApprovalStep
    extra = 0
    readonly_fields = ("document", "order", "approver", "role", "status", "comment", "acted_at")


@admin.register(ApprovalRoute)
class ApprovalRouteAdmin(admin.ModelAdmin):
    list_display = ("document", "status", "created_by", "created_at", "completed_at")
    list_filter = ("status",)
    inlines = (ApprovalStepInline,)


@admin.register(ApprovalAction)
class ApprovalActionAdmin(admin.ModelAdmin):
    list_display = ("document", "step", "actor", "action", "created_at")
    list_filter = ("action",)
    readonly_fields = ("document", "step", "actor", "action", "comment", "created_at")


@admin.register(DocumentComment)
class DocumentCommentAdmin(admin.ModelAdmin):
    list_display = ("document", "author", "comment_type", "created_at")
    list_filter = ("comment_type",)
    search_fields = ("text", "document__title")


@admin.register(DocumentHistory)
class DocumentHistoryAdmin(admin.ModelAdmin):
    list_display = ("document", "user", "action", "created_at")
    list_filter = ("action",)
    search_fields = ("document__title", "description")
    readonly_fields = (
        "document",
        "user",
        "action",
        "old_values",
        "new_values",
        "description",
        "created_at",
    )
