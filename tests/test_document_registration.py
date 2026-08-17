from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import IntegrityError, close_old_connections, transaction

from apps.accounts.models import User
from apps.audit.constants import AuditAction
from apps.audit.models import AuditLog
from apps.documents.models import (
    Document,
    DocumentCategory,
    DocumentNumberCounter,
    DocumentStatus,
)
from apps.documents.services import RegistrationService

pytestmark = pytest.mark.django_db


@pytest.fixture
def registration_category(admin):
    return DocumentCategory.objects.create(
        name="Приказы",
        code="orders",
        retention_period_days=1825,
        created_by=admin,
        updated_by=admin,
    )


@pytest.fixture
def approved_document(employee, child_department, registration_category):
    return Document.objects.create(
        title="Приказ о назначении",
        document_type="order",
        category=registration_category,
        author=employee,
        department=child_department,
        status=DocumentStatus.APPROVED,
    )


@pytest.fixture
def office(user_factory, child_department):
    return user_factory(email="office@esu.kg", role_code="office", department=child_department)


@pytest.fixture
def office_client(auth_client, office):
    return auth_client(office)


class TestDocumentRegistrationApi:
    def test_office_registers_approved_document(self, office_client, approved_document):
        response = office_client.post(f"/api/v1/documents/{approved_document.id}/register/")

        assert response.status_code == 200
        number = response.json()["data"]["registration_number"]
        assert number.startswith("ESU-IT-")
        assert number.endswith("-000001")
        audit = AuditLog.objects.get(action=AuditAction.DOCUMENT_REGISTER)
        assert audit.object_id == str(approved_document.id)
        assert audit.metadata["registration_number"] == number

    def test_admin_can_register(self, admin_client, approved_document):
        assert (
            admin_client.post(f"/api/v1/documents/{approved_document.id}/register/").status_code
            == 200
        )

    def test_employee_cannot_register(self, employee_client, approved_document):
        response = employee_client.post(f"/api/v1/documents/{approved_document.id}/register/")
        assert response.status_code == 403

    def test_only_approved_document_can_be_registered(self, office_client, approved_document):
        approved_document.status = DocumentStatus.IN_REVIEW
        approved_document.save(update_fields=["status"])
        response = office_client.post(f"/api/v1/documents/{approved_document.id}/register/")
        assert response.status_code == 400

    def test_cannot_register_twice(self, office_client, approved_document):
        office_client.post(f"/api/v1/documents/{approved_document.id}/register/")
        response = office_client.post(f"/api/v1/documents/{approved_document.id}/register/")
        assert response.status_code == 400

    def test_registration_number_cannot_be_changed(self, admin_client, approved_document):
        registered = admin_client.post(
            f"/api/v1/documents/{approved_document.id}/register/"
        ).json()["data"]["registration_number"]
        approved_document.status = DocumentStatus.RETURNED
        approved_document.save(update_fields=["status"])

        admin_client.patch(
            f"/api/v1/documents/{approved_document.id}/",
            {"registration_number": "MANUAL-1", "title": "Изменено"},
            format="json",
        )
        approved_document.refresh_from_db()
        assert approved_document.registration_number == registered

    def test_sequence_increments(self, office_client, approved_document):
        second = Document.objects.create(
            title="Второй приказ",
            document_type="order",
            category=approved_document.category,
            author=approved_document.author,
            department=approved_document.department,
            status=DocumentStatus.APPROVED,
        )
        first_number = office_client.post(
            f"/api/v1/documents/{approved_document.id}/register/"
        ).json()["data"]["registration_number"]
        second_number = office_client.post(f"/api/v1/documents/{second.id}/register/").json()[
            "data"
        ]["registration_number"]

        assert first_number.endswith("-000001")
        assert second_number.endswith("-000002")
        assert DocumentNumberCounter.objects.get().last_number == 2

    def test_number_format_comes_from_settings(
        self, settings, office_client, approved_document
    ):
        settings.DOCUMENT_NUMBER_FORMAT = "DOC-{year}-{department}-{number}"
        settings.DOCUMENT_NUMBER_PADDING = 4

        number = office_client.post(
            f"/api/v1/documents/{approved_document.id}/register/"
        ).json()["data"]["registration_number"]

        assert number == "DOC-2026-IT-0001"


def test_counter_is_unique_per_department_and_year(child_department):
    DocumentNumberCounter.objects.create(
        department=child_department, year=2026, last_number=1
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        DocumentNumberCounter.objects.create(
            department=child_department, year=2026, last_number=2
        )


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_registration_generates_unique_sequential_numbers(
    office,
    employee,
    child_department,
    registration_category,
):
    documents = [
        Document.objects.create(
            title=f"Конкурентный документ {index}",
            document_type="order",
            category=registration_category,
            author=employee,
            department=child_department,
            status=DocumentStatus.APPROVED,
        )
        for index in range(5)
    ]

    def register(document_id):
        close_old_connections()
        try:
            thread_user = User.objects.get(pk=office.pk)
            document = Document.objects.get(pk=document_id)
            return RegistrationService.register(document, thread_user).registration_number
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=5) as executor:
        numbers = list(executor.map(register, [document.id for document in documents]))

    assert len(numbers) == len(set(numbers)) == 5
    assert sorted(int(number.rsplit("-", 1)[1]) for number in numbers) == [1, 2, 3, 4, 5]
    assert DocumentNumberCounter.objects.get(
        department=child_department, year=2026
    ).last_number == 5
