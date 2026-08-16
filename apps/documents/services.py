from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, QuerySet
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User, UserStatus
from apps.audit.constants import AuditAction
from apps.audit.services import log_action
from apps.notifications.models import NotificationType
from apps.notifications.services import NotificationService

from .access import DocumentAccessService
from .models import (
    ApprovalAction,
    ApprovalActionType,
    ApprovalRoute,
    ApprovalRouteSource,
    ApprovalRouteStatus,
    ApprovalRouteTemplate,
    ApprovalStep,
    ApprovalStepStatus,
    ApprovalTemplateApproverType,
    ApprovalTemplateDepartmentRelation,
    Document,
    DocumentCategory,
    DocumentCategoryStatus,
    DocumentComment,
    DocumentCommentType,
    DocumentFile,
    DocumentHistory,
    DocumentHistoryAction,
    DocumentNumberCounter,
    DocumentStatus,
)
from .transitions import DocumentStateMachine, DocumentTransitionAction


class DocumentCategoryService:
    @staticmethod
    @transaction.atomic
    def set_status(category: DocumentCategory, status: str, user) -> DocumentCategory:
        category.status = status
        category.updated_by = user
        category.save(update_fields=["status", "updated_by", "updated_at"])
        return category

    @staticmethod
    @transaction.atomic
    def delete(category: DocumentCategory) -> None:
        if hasattr(category, "documents") and category.documents.exists():
            raise ValidationError(
                "Нельзя удалить категорию с документами. Используйте деактивацию."
            )
        category.delete()

    @classmethod
    def activate(cls, category: DocumentCategory, user) -> DocumentCategory:
        return cls.set_status(category, DocumentCategoryStatus.ACTIVE, user)

    @classmethod
    def deactivate(cls, category: DocumentCategory, user) -> DocumentCategory:
        return cls.set_status(category, DocumentCategoryStatus.INACTIVE, user)


class DocumentService:
    EDITABLE_STATUSES = DocumentAccessService.EDITABLE_STATUSES

    @staticmethod
    def visible_to(user, queryset: QuerySet | None = None) -> QuerySet:
        return DocumentAccessService.visible_to(user, queryset)

    @classmethod
    def ensure_can_edit(cls, document: Document, user) -> None:
        if document.status not in cls.EDITABLE_STATUSES:
            raise ValidationError("Документ в этом статусе нельзя редактировать")
        if not DocumentAccessService.can_edit(user, document):
            raise PermissionDenied("Редактировать документ может только автор или администратор")

    @classmethod
    def ensure_can_delete(cls, document: Document, user) -> None:
        if document.status != DocumentStatus.DRAFT:
            raise ValidationError("После отправки документ нельзя удалить")
        if not DocumentAccessService.can_delete(user, document):
            raise PermissionDenied("Удалить документ может только автор или администратор")

    @staticmethod
    @transaction.atomic
    def complete(document: Document, user) -> Document:
        document = Document.objects.select_for_update().get(pk=document.pk)
        target_status = DocumentStateMachine.target_status(
            document, DocumentTransitionAction.COMPLETE
        )
        if not DocumentAccessService.can_complete(user, document):
            raise PermissionDenied("Недостаточно прав для завершения документа")
        document.status = target_status
        document.completed_at = timezone.now()
        document.save(update_fields=["status", "completed_at", "updated_at"])
        HistoryService.record(
            document,
            user,
            DocumentHistoryAction.COMPLETED,
            old_values={"status": DocumentStatus.APPROVED},
            new_values={"status": document.status, "completed_at": document.completed_at},
            description="Документ завершён",
        )
        return document

    @staticmethod
    @transaction.atomic
    def archive(document: Document, user) -> Document:
        document = Document.objects.select_for_update().select_related("author").get(
            pk=document.pk
        )
        target_status = DocumentStateMachine.target_status(
            document, DocumentTransitionAction.ARCHIVE
        )
        if not DocumentAccessService.can_archive(user, document):
            raise PermissionDenied("Недостаточно прав для архивирования документа")
        previous_status = document.status
        document.status = target_status
        document.archived_at = timezone.now()
        document.save(update_fields=["status", "archived_at", "updated_at"])
        HistoryService.record(
            document,
            user,
            DocumentHistoryAction.ARCHIVED,
            old_values={"status": previous_status},
            new_values={"status": document.status, "archived_at": document.archived_at},
            description="Документ архивирован",
        )
        if document.author_id != user.id:
            NotificationService.create(
                recipient=document.author,
                notification_type=NotificationType.DOCUMENT_ARCHIVED,
                title="Документ архивирован",
                message=f"Документ «{document.title}» перемещён в архив.",
                document=document,
            )
        return document

    @staticmethod
    @transaction.atomic
    def restore(document: Document, user) -> Document:
        document = Document.objects.select_for_update().get(pk=document.pk)
        restored_status = DocumentStateMachine.target_status(
            document, DocumentTransitionAction.RESTORE
        )
        if not DocumentAccessService.can_restore(user, document):
            raise PermissionDenied("Недостаточно прав для восстановления документа")
        document.status = restored_status
        document.archived_at = None
        document.save(update_fields=["status", "archived_at", "updated_at"])
        HistoryService.record(
            document,
            user,
            DocumentHistoryAction.RESTORED,
            old_values={"status": DocumentStatus.ARCHIVED},
            new_values={"status": restored_status},
            description="Документ восстановлен из архива",
        )
        return document


class RegistrationService:
    @staticmethod
    def _locked_counter(department, year: int) -> DocumentNumberCounter:
        try:
            return DocumentNumberCounter.objects.select_for_update().get(
                department=department, year=year
            )
        except DocumentNumberCounter.DoesNotExist:
            try:
                # Savepoint keeps the outer transaction usable if another request
                # creates the same unique counter at exactly this moment.
                with transaction.atomic():
                    return DocumentNumberCounter.objects.create(
                        department=department, year=year, last_number=0
                    )
            except IntegrityError:
                return DocumentNumberCounter.objects.select_for_update().get(
                    department=department, year=year
                )

    @classmethod
    @transaction.atomic
    def register(cls, document: Document, user) -> Document:
        if not DocumentAccessService.can_register(user, document):
            raise PermissionDenied("Недостаточно прав для регистрации документа")

        document = (
            Document.objects.select_for_update()
            .select_related("category", "department")
            .get(pk=document.pk)
        )
        if document.registration_number:
            raise ValidationError("Документ уже зарегистрирован")
        if document.status != DocumentStatus.APPROVED:
            raise ValidationError("Зарегистрировать можно только согласованный документ")

        year = timezone.localdate().year
        counter = cls._locked_counter(document.department, year)
        counter.last_number += 1
        counter.save(update_fields=["last_number", "updated_at"])

        padded_number = str(counter.last_number).zfill(settings.DOCUMENT_NUMBER_PADDING)
        document.registration_number = settings.DOCUMENT_NUMBER_FORMAT.format(
            prefix=settings.DOCUMENT_NUMBER_PREFIX,
            department=document.department.code.upper(),
            year=year,
            number=padded_number,
        )
        document.save(update_fields=["registration_number", "updated_at"])
        HistoryService.record(
            document,
            user,
            DocumentHistoryAction.REGISTERED,
            old_values={"registration_number": None},
            new_values={"registration_number": document.registration_number},
            description=f"Документ зарегистрирован: {document.registration_number}",
        )
        log_action(
            user=user,
            action=AuditAction.DOCUMENT_REGISTER,
            obj=document,
            description=f"Документ зарегистрирован: {document.registration_number}",
            metadata={
                "registration_number": document.registration_number,
                "department_id": str(document.department_id),
                "category_id": str(document.category_id),
            },
        )
        return document


class FileService:
    ALLOWED_MIME_TYPES = {
        ".pdf": {"application/pdf"},
        ".doc": {"application/msword"},
        ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        ".png": {"image/png"},
        ".jpg": {"image/jpeg"},
        ".jpeg": {"image/jpeg"},
    }

    @staticmethod
    def _has_valid_signature(uploaded_file, extension: str) -> bool:
        position = uploaded_file.tell()
        try:
            header = uploaded_file.read(8)
            uploaded_file.seek(0)
            if extension == ".pdf":
                return header.startswith(b"%PDF-")
            if extension == ".png":
                return header == b"\x89PNG\r\n\x1a\n"
            if extension in {".jpg", ".jpeg"}:
                return header.startswith(b"\xff\xd8\xff")
            if extension == ".doc":
                return header == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
            if extension in {".docx", ".xlsx"}:
                try:
                    with ZipFile(uploaded_file) as archive:
                        prefix = "word/" if extension == ".docx" else "xl/"
                        return any(name.startswith(prefix) for name in archive.namelist())
                except BadZipFile:
                    return False
            return False
        finally:
            uploaded_file.seek(position)

    @classmethod
    def validate_upload(cls, uploaded_file) -> tuple[str, str]:
        original_name = Path(uploaded_file.name).name
        extension = Path(original_name).suffix.lower()
        if extension not in cls.ALLOWED_MIME_TYPES:
            raise ValidationError(
                "Недопустимый формат файла. Разрешены PDF, DOC, DOCX, XLSX, PNG, JPG и JPEG."
            )

        mime_type = (getattr(uploaded_file, "content_type", "") or "").lower()
        if mime_type not in cls.ALLOWED_MIME_TYPES[extension]:
            raise ValidationError("MIME-тип файла не соответствует его расширению")

        if uploaded_file.size > settings.MAX_DOCUMENT_FILE_SIZE:
            max_megabytes = settings.MAX_DOCUMENT_FILE_SIZE // (1024 * 1024)
            raise ValidationError(f"Размер файла не должен превышать {max_megabytes} МБ")
        if uploaded_file.size == 0:
            raise ValidationError("Нельзя загрузить пустой файл")
        if not cls._has_valid_signature(uploaded_file, extension):
            raise ValidationError("Содержимое файла не соответствует заявленному формату")
        return extension.removeprefix("."), mime_type

    @classmethod
    @transaction.atomic
    def upload(cls, document: Document, uploaded_file, user, is_main=False) -> DocumentFile:
        document = Document.objects.select_for_update().get(pk=document.pk)
        if not DocumentAccessService.can_upload_file(user, document):
            DocumentService.ensure_can_edit(document, user)
        file_type, mime_type = cls.validate_upload(uploaded_file)

        existing_files_count = document.files.count()
        if existing_files_count >= settings.MAX_DOCUMENT_FILES:
            raise ValidationError(
                f"К одному документу можно прикрепить не более {settings.MAX_DOCUMENT_FILES} файлов"
            )

        existing_files = existing_files_count > 0
        make_main = is_main or not existing_files
        if make_main:
            document.files.filter(is_main=True).update(is_main=False)

        document_file = DocumentFile.objects.create(
            document=document,
            file=uploaded_file,
            original_name=Path(uploaded_file.name).name,
            file_type=file_type,
            mime_type=mime_type,
            size=uploaded_file.size,
            is_main=make_main,
            uploaded_by=user,
        )
        HistoryService.record(
            document,
            user,
            DocumentHistoryAction.FILE_UPLOADED,
            new_values={
                "file_id": document_file.id,
                "original_name": document_file.original_name,
                "size": document_file.size,
            },
            description=f"Загружен файл {document_file.original_name}",
        )
        return document_file

    @staticmethod
    @transaction.atomic
    def make_main(document_file: DocumentFile, user) -> DocumentFile:
        document = Document.objects.select_for_update().get(pk=document_file.document_id)
        if not DocumentAccessService.can_upload_file(user, document):
            DocumentService.ensure_can_edit(document, user)
        document_file = DocumentFile.objects.select_for_update().get(pk=document_file.pk)
        if document_file.is_main:
            return document_file

        document.files.filter(is_main=True).update(is_main=False)
        document_file.is_main = True
        document_file.save(update_fields=["is_main"])
        HistoryService.record(
            document,
            user,
            DocumentHistoryAction.UPDATED,
            new_values={"main_file_id": document_file.id},
            description=f"Файл {document_file.original_name} назначен основным",
        )
        return document_file

    @staticmethod
    @transaction.atomic
    def delete(document_file: DocumentFile, user) -> None:
        document = Document.objects.select_for_update().get(pk=document_file.document_id)
        if not DocumentAccessService.can_delete_file(user, document):
            DocumentService.ensure_can_edit(document, user)
        document_file = DocumentFile.objects.select_for_update().get(pk=document_file.pk)
        HistoryService.record(
            document_file.document,
            user,
            DocumentHistoryAction.FILE_DELETED,
            old_values={
                "file_id": document_file.id,
                "original_name": document_file.original_name,
                "size": document_file.size,
            },
            description=f"Удалён файл {document_file.original_name}",
        )
        storage = document_file.file.storage
        stored_name = document_file.file.name
        replacement = None
        if document_file.is_main:
            replacement = (
                document.files.exclude(pk=document_file.pk)
                .order_by("created_at")
                .first()
            )
        document_file.delete()
        if replacement is not None:
            replacement.is_main = True
            replacement.save(update_fields=["is_main"])
        transaction.on_commit(lambda: storage.delete(stored_name))


class ApprovalService:
    @staticmethod
    def _locked_document(document: Document) -> Document:
        return Document.objects.select_for_update().get(pk=document.pk)

    @staticmethod
    def _ensure_current_approver(step: ApprovalStep, user) -> None:
        if not DocumentAccessService.can_approve(user, step.document):
            raise PermissionDenied("Действие доступно только текущему согласующему")

    @staticmethod
    def _is_active_approver(user) -> bool:
        return bool(
            user
            and user.status == UserStatus.ACTIVE
            and user.is_active
            and not user.is_deleted
        )

    @classmethod
    def _resolve_template_step(cls, document: Document, step):
        if step.approver_type == ApprovalTemplateApproverType.SPECIFIC_USER:
            return step.specific_user
        if step.approver_type == ApprovalTemplateApproverType.DOCUMENT_RESPONSIBLE:
            return document.responsible
        if step.approver_type == ApprovalTemplateApproverType.DEPARTMENT_MANAGER:
            department = (
                document.author.department
                if step.department_relation
                == ApprovalTemplateDepartmentRelation.AUTHOR_DEPARTMENT
                else document.department
            )
            return department.manager if department else None
        if step.approver_type == ApprovalTemplateApproverType.ROLE:
            candidates = User.objects.filter(
                role=step.role,
                status=UserStatus.ACTIVE,
                is_active=True,
            ).select_related("role")
            return (
                candidates.filter(department=document.department).order_by("email").first()
                or candidates.order_by("email").first()
            )
        return None

    @classmethod
    def _resolve_route(cls, document: Document, manual_approvers: list):
        if manual_approvers:
            ids = [approver.id for approver in manual_approvers]
            if len(ids) != len(set(ids)):
                raise ValidationError("Согласующие в маршруте не должны повторяться")
            if not all(cls._is_active_approver(approver) for approver in manual_approvers):
                raise ValidationError("Все согласующие должны быть активны")
            return (
                manual_approvers,
                None,
                ApprovalRouteSource.MANUAL,
                {
                    "source": ApprovalRouteSource.MANUAL,
                    "approvers": [str(approver.id) for approver in manual_approvers],
                },
            )

        template = (
            ApprovalRouteTemplate.objects.filter(
                category=document.category, is_active=True
            )
            .prefetch_related("steps__role", "steps__specific_user")
            .first()
        )
        if template is None:
            raise ValidationError(
                "Передайте согласующих вручную или настройте активный шаблон категории"
            )

        approvers = []
        snapshot_steps = []
        seen_ids = set()
        for step in template.steps.all():
            approver = cls._resolve_template_step(document, step)
            if not cls._is_active_approver(approver):
                if step.is_required:
                    raise ValidationError(
                        f"Не удалось определить активного согласующего для шага {step.order}"
                    )
                continue
            if approver.id in seen_ids:
                raise ValidationError(
                    f"Пользователь {approver.email} повторяется в шаблоне согласования"
                )
            seen_ids.add(approver.id)
            approvers.append(approver)
            snapshot_steps.append(
                {
                    "template_order": step.order,
                    "route_order": len(approvers),
                    "approver_type": step.approver_type,
                    "role_id": str(step.role_id) if step.role_id else None,
                    "specific_user_id": (
                        str(step.specific_user_id) if step.specific_user_id else None
                    ),
                    "department_relation": step.department_relation,
                    "is_required": step.is_required,
                    "resolved_approver_id": str(approver.id),
                }
            )

        if not approvers:
            raise ValidationError("Шаблон категории не создал ни одного шага согласования")
        return (
            approvers,
            template,
            ApprovalRouteSource.CATEGORY_TEMPLATE,
            {
                "source": ApprovalRouteSource.CATEGORY_TEMPLATE,
                "template_id": str(template.id),
                "template_name": template.name,
                "steps": snapshot_steps,
            },
        )

    @classmethod
    @transaction.atomic
    def submit(cls, document: Document, user, approvers: list) -> ApprovalRoute:
        document = cls._locked_document(document)
        transition_action = DocumentStateMachine.submission_action(document)
        target_status = DocumentStateMachine.target_status(document, transition_action)
        DocumentService.ensure_can_edit(document, user)
        previous_status = document.status
        if document.category.requires_file and not document.files.exists():
            raise ValidationError("Для этой категории необходимо загрузить файл")
        approvers, template, route_source, route_snapshot = cls._resolve_route(
            document, approvers
        )

        ApprovalRoute.objects.filter(document=document, status=ApprovalRouteStatus.ACTIVE).update(
            status=ApprovalRouteStatus.CANCELLED, completed_at=timezone.now()
        )
        ApprovalStep.objects.filter(
            document=document,
            route__status=ApprovalRouteStatus.CANCELLED,
            status__in=[ApprovalStepStatus.PENDING, ApprovalStepStatus.CURRENT],
        ).update(status=ApprovalStepStatus.CANCELLED)

        route = ApprovalRoute.objects.create(
            document=document,
            created_by=user,
            source=route_source,
            template=template,
            template_snapshot=route_snapshot,
        )
        ApprovalStep.objects.bulk_create(
            [
                ApprovalStep(
                    route=route,
                    document=document,
                    order=order,
                    approver=approver,
                    role_id=approver.role_id,
                    status=(
                        ApprovalStepStatus.CURRENT if order == 1 else ApprovalStepStatus.PENDING
                    ),
                )
                for order, approver in enumerate(approvers, start=1)
            ]
        )

        document.status = target_status
        document.submitted_at = timezone.now()
        document.approved_at = None
        document.current_approval_step = 1
        document.save(
            update_fields=[
                "status",
                "submitted_at",
                "approved_at",
                "current_approval_step",
                "updated_at",
            ]
        )
        history_action = (
            DocumentHistoryAction.RESUBMITTED
            if previous_status == DocumentStatus.RETURNED
            else DocumentHistoryAction.SUBMITTED
        )
        HistoryService.record(
            document,
            user,
            history_action,
            old_values={"status": previous_status},
            new_values={
                "status": document.status,
                "route_id": route.id,
                "approvers": [approver.id for approver in approvers],
            },
            description=(
                "Документ повторно отправлен на согласование"
                if history_action == DocumentHistoryAction.RESUBMITTED
                else "Документ отправлен на согласование"
            ),
        )
        NotificationService.create(
            recipient=document.author,
            notification_type=NotificationType.DOCUMENT_SUBMITTED,
            title="Документ отправлен на согласование",
            message=f"Документ «{document.title}» отправлен по маршруту согласования.",
            document=document,
        )
        first_approver = approvers[0]
        NotificationService.create(
            recipient=first_approver,
            notification_type=NotificationType.APPROVAL_REQUIRED,
            title="Требуется согласование",
            message=f"Вам назначен документ «{document.title}» на согласование.",
            document=document,
        )
        return route

    @classmethod
    @transaction.atomic
    def approve(cls, document: Document, user, comment="") -> ApprovalRoute:
        document = cls._locked_document(document)
        approved_status = DocumentStateMachine.target_status(
            document, DocumentTransitionAction.APPROVE
        )
        route = ApprovalRoute.objects.select_for_update().get(
            document=document, status=ApprovalRouteStatus.ACTIVE
        )
        try:
            step = ApprovalStep.objects.select_for_update().get(
                route=route, status=ApprovalStepStatus.CURRENT
            )
        except ApprovalStep.DoesNotExist as exc:
            raise ValidationError("Текущий шаг согласования не найден") from exc
        cls._ensure_current_approver(step, user)

        now = timezone.now()
        step.status = ApprovalStepStatus.APPROVED
        step.comment = comment
        step.acted_at = now
        step.save(update_fields=["status", "comment", "acted_at"])
        ApprovalAction.objects.create(
            document=document,
            step=step,
            actor=user,
            action=ApprovalActionType.APPROVE,
            comment=comment,
        )
        if comment:
            DocumentComment.objects.create(
                document=document,
                author=user,
                text=comment,
                comment_type=DocumentCommentType.APPROVAL,
            )

        next_step = (
            ApprovalStep.objects.select_for_update()
            .filter(route=route, status=ApprovalStepStatus.PENDING, order__gt=step.order)
            .order_by("order")
            .first()
        )
        if next_step:
            next_step.status = ApprovalStepStatus.CURRENT
            next_step.save(update_fields=["status"])
            document.current_approval_step = next_step.order
            document.save(update_fields=["current_approval_step", "updated_at"])
            NotificationService.create(
                recipient=next_step.approver,
                notification_type=NotificationType.APPROVAL_REQUIRED,
                title="Требуется согласование",
                message=f"Вам назначен документ «{document.title}» на согласование.",
                document=document,
            )
        else:
            route.status = ApprovalRouteStatus.COMPLETED
            route.completed_at = now
            route.save(update_fields=["status", "completed_at"])
            document.status = approved_status
            document.approved_at = now
            document.current_approval_step = None
            document.save(
                update_fields=[
                    "status",
                    "approved_at",
                    "current_approval_step",
                    "updated_at",
                ]
            )
            NotificationService.notify_many(
                [document.author, document.responsible],
                notification_type=NotificationType.DOCUMENT_APPROVED,
                title="Документ согласован",
                message=f"Документ «{document.title}» успешно согласован.",
                document=document,
            )
        HistoryService.record(
            document,
            user,
            DocumentHistoryAction.APPROVED,
            old_values={"approval_step": step.order, "step_status": "current"},
            new_values={
                "approval_step": step.order,
                "step_status": step.status,
                "document_status": document.status,
            },
            description=f"Согласован шаг {step.order}",
        )
        return route

    @classmethod
    @transaction.atomic
    def return_document(cls, document: Document, user, comment: str) -> ApprovalRoute:
        document = cls._locked_document(document)
        returned_status = DocumentStateMachine.target_status(
            document, DocumentTransitionAction.RETURN
        )
        route = ApprovalRoute.objects.select_for_update().get(
            document=document, status=ApprovalRouteStatus.ACTIVE
        )
        try:
            step = ApprovalStep.objects.select_for_update().get(
                route=route, status=ApprovalStepStatus.CURRENT
            )
        except ApprovalStep.DoesNotExist as exc:
            raise ValidationError("Текущий шаг согласования не найден") from exc
        cls._ensure_current_approver(step, user)

        now = timezone.now()
        step.status = ApprovalStepStatus.RETURNED
        step.comment = comment
        step.acted_at = now
        step.save(update_fields=["status", "comment", "acted_at"])
        route.steps.filter(status=ApprovalStepStatus.PENDING).update(
            status=ApprovalStepStatus.CANCELLED
        )
        ApprovalAction.objects.create(
            document=document,
            step=step,
            actor=user,
            action=ApprovalActionType.RETURN,
            comment=comment,
        )
        DocumentComment.objects.create(
            document=document,
            author=user,
            text=comment,
            comment_type=DocumentCommentType.RETURN_REASON,
        )

        route.status = ApprovalRouteStatus.RETURNED
        route.completed_at = now
        route.save(update_fields=["status", "completed_at"])
        document.status = returned_status
        document.current_approval_step = None
        document.save(update_fields=["status", "current_approval_step", "updated_at"])
        HistoryService.record(
            document,
            user,
            DocumentHistoryAction.RETURNED,
            old_values={"status": DocumentStatus.IN_REVIEW, "approval_step": step.order},
            new_values={"status": document.status, "reason": comment},
            description=f"Документ возвращён на шаге {step.order}",
        )
        NotificationService.create(
            recipient=document.author,
            notification_type=NotificationType.DOCUMENT_RETURNED,
            title="Документ возвращён",
            message=f"Документ «{document.title}» возвращён: {comment}",
            document=document,
        )
        return route


class CommentService:
    @staticmethod
    @transaction.atomic
    def create(document: Document, user, text: str) -> DocumentComment:
        if document.status == DocumentStatus.ARCHIVED:
            raise ValidationError("Архивированный документ доступен только для чтения")
        comment = DocumentComment.objects.create(
            document=document,
            author=user,
            text=text,
            comment_type=DocumentCommentType.GENERAL,
        )
        recipients = [
            recipient
            for recipient in [document.author, document.responsible]
            if recipient and recipient.id != user.id
        ]
        NotificationService.notify_many(
            recipients,
            notification_type=NotificationType.COMMENT_ADDED,
            title="Новый комментарий к документу",
            message=f"К документу «{document.title}» добавлен комментарий.",
            document=document,
        )
        return comment

    @staticmethod
    def ensure_editable(comment: DocumentComment, user) -> None:
        if comment.comment_type != DocumentCommentType.GENERAL:
            raise ValidationError("Системные комментарии и причины возврата нельзя изменять")
        if comment.author_id != user.id:
            raise PermissionDenied("Можно изменять только собственный комментарий")
        if comment.document.status == DocumentStatus.ARCHIVED:
            raise ValidationError("Архивированный документ доступен только для чтения")

    @classmethod
    @transaction.atomic
    def update(cls, comment: DocumentComment, user, text: str) -> DocumentComment:
        cls.ensure_editable(comment, user)
        comment.text = text
        comment.save(update_fields=["text", "updated_at"])
        return comment

    @classmethod
    @transaction.atomic
    def delete(cls, comment: DocumentComment, user) -> None:
        cls.ensure_editable(comment, user)
        comment.delete()


class HistoryService:
    TRACKED_FIELDS = (
        "registration_number",
        "title",
        "description",
        "document_type",
        "category_id",
        "department_id",
        "responsible_id",
        "priority",
        "status",
        "deadline",
    )

    @staticmethod
    def _normalize(value):
        if value is None or isinstance(value, str | int | float | bool):
            return value
        if isinstance(value, dict):
            return {key: HistoryService._normalize(item) for key, item in value.items()}
        if isinstance(value, list | tuple | set):
            return [HistoryService._normalize(item) for item in value]
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    @classmethod
    def snapshot(cls, document: Document) -> dict:
        return {field: cls._normalize(getattr(document, field)) for field in cls.TRACKED_FIELDS}

    @classmethod
    def normalize_mapping(cls, values: dict | None) -> dict:
        return {key: cls._normalize(value) for key, value in (values or {}).items()}

    @classmethod
    def record(
        cls,
        document: Document,
        user,
        action: str,
        old_values=None,
        new_values=None,
        description="",
    ) -> DocumentHistory:
        return DocumentHistory.objects.create(
            document=document,
            user=user,
            action=action,
            old_values=cls.normalize_mapping(old_values),
            new_values=cls.normalize_mapping(new_values),
            description=description,
        )


class DashboardService:
    LIST_LIMIT = 5
    ACTIONS_LIMIT = 10

    @staticmethod
    def documents_for(user) -> QuerySet:
        queryset = Document.objects.all()
        if not (user.is_superuser or user.is_admin_role):
            role_code = user.role.code if user.role_id else None
            if role_code == "employee":
                queryset = queryset.filter(author=user)
            else:
                queryset = DocumentService.visible_to(user, queryset)

        return queryset.select_related("category", "author", "department", "responsible")

    @classmethod
    def build(cls, user) -> dict:
        documents = cls.documents_for(user)
        counters = documents.aggregate(
            total_documents=Count("id"),
            in_review=Count("id", filter=Q(status=DocumentStatus.IN_REVIEW)),
            returned=Count("id", filter=Q(status=DocumentStatus.RETURNED)),
            overdue=Count("id", filter=Q(status=DocumentStatus.OVERDUE)),
            completed=Count("id", filter=Q(status=DocumentStatus.COMPLETED)),
        )

        approval_tasks = ApprovalStep.objects.filter(status=ApprovalStepStatus.CURRENT)
        if not (user.is_superuser or user.is_admin_role):
            approval_tasks = approval_tasks.filter(approver=user)

        visible_ids = documents.values("id")
        return {
            **counters,
            "approval_tasks": approval_tasks.count(),
            "recent_documents": documents.order_by("-created_at")[: cls.LIST_LIMIT],
            "upcoming_deadlines": documents.filter(
                deadline__gte=timezone.now(),
            )
            .exclude(status__in=[DocumentStatus.COMPLETED, DocumentStatus.ARCHIVED])
            .order_by("deadline")[: cls.LIST_LIMIT],
            "recent_actions": DocumentHistory.objects.filter(document_id__in=visible_ids)
            .select_related("document", "user")
            .order_by("-created_at")[: cls.ACTIONS_LIMIT],
        }
