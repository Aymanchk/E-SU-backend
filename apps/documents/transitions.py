from apps.common.exceptions import StructuredAPIException

from .models import Document, DocumentStatus


class DocumentTransitionAction:
    SUBMIT = "submit"
    RESUBMIT = "resubmit"
    APPROVE = "approve"
    RETURN = "return"
    COMPLETE = "complete"
    ARCHIVE = "archive"
    RESTORE = "restore"


class DocumentStateMachine:
    TRANSITIONS = {
        DocumentTransitionAction.SUBMIT: {
            DocumentStatus.DRAFT: DocumentStatus.IN_REVIEW,
        },
        DocumentTransitionAction.RESUBMIT: {
            DocumentStatus.RETURNED: DocumentStatus.IN_REVIEW,
        },
        DocumentTransitionAction.APPROVE: {
            DocumentStatus.IN_REVIEW: DocumentStatus.APPROVED,
        },
        DocumentTransitionAction.RETURN: {
            DocumentStatus.IN_REVIEW: DocumentStatus.RETURNED,
        },
        DocumentTransitionAction.COMPLETE: {
            DocumentStatus.APPROVED: DocumentStatus.COMPLETED,
        },
        DocumentTransitionAction.ARCHIVE: {
            DocumentStatus.COMPLETED: DocumentStatus.ARCHIVED,
        },
        DocumentTransitionAction.RESTORE: {
            DocumentStatus.ARCHIVED: DocumentStatus.COMPLETED,
        },
    }
    ACTION_LABELS = {
        DocumentTransitionAction.SUBMIT: "отправить на согласование",
        DocumentTransitionAction.RESUBMIT: "повторно отправить на согласование",
        DocumentTransitionAction.APPROVE: "согласовать",
        DocumentTransitionAction.RETURN: "вернуть",
        DocumentTransitionAction.COMPLETE: "завершить",
        DocumentTransitionAction.ARCHIVE: "архивировать",
        DocumentTransitionAction.RESTORE: "восстановить",
    }

    @classmethod
    def target_status(cls, document: Document, action: str) -> str:
        target = cls.TRANSITIONS.get(action, {}).get(document.status)
        if target is None:
            label = cls.ACTION_LABELS.get(action, action)
            raise StructuredAPIException(
                code="invalid_document_transition",
                message=(
                    f"Документ нельзя {label} из текущего статуса"
                ),
                details={
                    "current_status": document.status,
                    "requested_action": action,
                },
            )
        return target

    @classmethod
    def submission_action(cls, document: Document) -> str:
        if document.status == DocumentStatus.RETURNED:
            return DocumentTransitionAction.RESUBMIT
        return DocumentTransitionAction.SUBMIT
