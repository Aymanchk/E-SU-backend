from django.db.models import Q, QuerySet

from .models import ApprovalStepStatus, Document, DocumentStatus


class DocumentAccessService:
    """Single source of truth for document object-level permissions."""

    EDITABLE_STATUSES = {DocumentStatus.DRAFT, DocumentStatus.RETURNED}

    @staticmethod
    def _is_admin(user) -> bool:
        return bool(user.is_superuser or user.is_admin_role)

    @classmethod
    def visible_to(cls, user, queryset: QuerySet | None = None) -> QuerySet:
        queryset = queryset if queryset is not None else Document.objects.all()
        if cls._is_admin(user):
            return queryset

        role_code = user.role.code if user.role_id else None
        participant = Q(author=user) | Q(responsible=user) | Q(approval_steps__approver=user)
        if role_code == "manager":
            return queryset.filter(participant | Q(department=user.department)).distinct()
        if role_code == "office":
            return queryset.filter(
                participant
                | Q(
                    status__in=[
                        DocumentStatus.IN_REVIEW,
                        DocumentStatus.APPROVED,
                        DocumentStatus.COMPLETED,
                        DocumentStatus.OVERDUE,
                        DocumentStatus.ARCHIVED,
                    ]
                )
            ).distinct()
        return queryset.filter(participant).distinct()

    @classmethod
    def can_view(cls, user, document: Document) -> bool:
        if cls._is_admin(user):
            return True
        if document.author_id == user.id or document.responsible_id == user.id:
            return True
        if document.approval_steps.filter(approver=user).exists():
            return True
        role_code = user.role.code if user.role_id else None
        if role_code == "manager" and document.department_id == user.department_id:
            return True
        return role_code == "office" and document.status in {
            DocumentStatus.IN_REVIEW,
            DocumentStatus.APPROVED,
            DocumentStatus.COMPLETED,
            DocumentStatus.OVERDUE,
            DocumentStatus.ARCHIVED,
        }

    @classmethod
    def can_edit(cls, user, document: Document) -> bool:
        return document.status in cls.EDITABLE_STATUSES and (
            cls._is_admin(user) or document.author_id == user.id
        )

    @classmethod
    def can_delete(cls, user, document: Document) -> bool:
        return document.status == DocumentStatus.DRAFT and (
            cls._is_admin(user) or document.author_id == user.id
        )

    @classmethod
    def can_submit(cls, user, document: Document) -> bool:
        return cls.can_edit(user, document) and (
            cls._is_admin(user) or user.has_permission("documents.create")
        )

    @classmethod
    def can_approve(cls, user, document: Document) -> bool:
        return (
            document.status == DocumentStatus.IN_REVIEW
            and document.approval_steps.filter(
                approver=user, status=ApprovalStepStatus.CURRENT
            ).exists()
        )

    @classmethod
    def can_return(cls, user, document: Document) -> bool:
        return cls.can_approve(user, document)

    @classmethod
    def can_register(cls, user, document: Document) -> bool:
        return cls._is_admin(user) or user.has_permission("documents.register")

    @classmethod
    def can_complete(cls, user, document: Document) -> bool:
        return document.status == DocumentStatus.APPROVED and (
            cls._is_admin(user)
            or document.responsible_id == user.id
            or user.has_permission("documents.edit")
        )

    @classmethod
    def can_archive(cls, user, document: Document) -> bool:
        return document.status == DocumentStatus.COMPLETED and (
            cls._is_admin(user) or user.has_permission("documents.archive")
        )

    @classmethod
    def can_restore(cls, user, document: Document) -> bool:
        return document.status == DocumentStatus.ARCHIVED and (
            cls._is_admin(user) or user.has_permission("documents.archive")
        )

    @classmethod
    def can_upload_file(cls, user, document: Document) -> bool:
        return cls.can_edit(user, document)

    @classmethod
    def can_download_file(cls, user, document: Document) -> bool:
        return cls.can_view(user, document)

    @classmethod
    def can_delete_file(cls, user, document: Document) -> bool:
        return cls.can_edit(user, document)

    @classmethod
    def can_comment(cls, user, document: Document) -> bool:
        return document.status != DocumentStatus.ARCHIVED and cls.can_view(user, document)

    @classmethod
    def can_view_history(cls, user, document: Document) -> bool:
        return cls.can_view(user, document)
