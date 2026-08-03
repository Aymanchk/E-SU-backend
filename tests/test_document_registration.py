import pytest
from django.db import IntegrityError, transaction

from apps.documents.models import (
    Document,
    DocumentCategory,
    DocumentNumberCounter,
    DocumentStatus,
)

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
    return user_factory(
        email="office@esu.kg", role_code="office", department=child_department
    )


@pytest.fixture
def office_client(auth_client, office):
    return auth_client(office)


class TestDocumentRegistrationApi:
    def test_office_registers_approved_document(self, office_client, approved_document):
        response = office_client.post(f"/api/documents/{approved_document.id}/register/")

        assert response.status_code == 200
        number = response.json()["data"]["registration_number"]
        assert number.startswith("ESU-ORDERS-")
        assert number.endswith("-000001")

    def test_admin_can_register(self, admin_client, approved_document):
        assert (
            admin_client.post(f"/api/documents/{approved_document.id}/register/").status_code
            == 200
        )

    def test_employee_cannot_register(self, employee_client, approved_document):
        response = employee_client.post(f"/api/documents/{approved_document.id}/register/")
        assert response.status_code == 403

    def test_only_approved_document_can_be_registered(
        self, office_client, approved_document
    ):
        approved_document.status = DocumentStatus.IN_REVIEW
        approved_document.save(update_fields=["status"])
        response = office_client.post(f"/api/documents/{approved_document.id}/register/")
        assert response.status_code == 400

    def test_cannot_register_twice(self, office_client, approved_document):
        office_client.post(f"/api/documents/{approved_document.id}/register/")
        response = office_client.post(f"/api/documents/{approved_document.id}/register/")
        assert response.status_code == 400

    def test_registration_number_cannot_be_changed(self, admin_client, approved_document):
        registered = admin_client.post(
            f"/api/documents/{approved_document.id}/register/"
        ).json()["data"]["registration_number"]
        approved_document.status = DocumentStatus.RETURNED
        approved_document.save(update_fields=["status"])

        admin_client.patch(
            f"/api/documents/{approved_document.id}/",
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
            f"/api/documents/{approved_document.id}/register/"
        ).json()["data"]["registration_number"]
        second_number = office_client.post(f"/api/documents/{second.id}/register/").json()[
            "data"
        ]["registration_number"]

        assert first_number.endswith("-000001")
        assert second_number.endswith("-000002")
        assert DocumentNumberCounter.objects.get().last_number == 2


def test_counter_is_unique_per_category_and_year(registration_category):
    DocumentNumberCounter.objects.create(
        category=registration_category, year=2026, last_number=1
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        DocumentNumberCounter.objects.create(
            category=registration_category, year=2026, last_number=2
        )
