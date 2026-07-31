from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.documents.models import Document, DocumentCategory, DocumentFile

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def local_file_storage(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.MAX_DOCUMENT_FILE_SIZE = 1024
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }


def upload(name="report.pdf", content=b"%PDF-1.4 test", mime="application/pdf"):
    return SimpleUploadedFile(name, content, content_type=mime)


@pytest.fixture
def document(employee, admin, child_department):
    category = DocumentCategory.objects.create(
        name="Файловая категория",
        code="file-category",
        retention_period_days=365,
        created_by=admin,
        updated_by=admin,
    )
    return Document.objects.create(
        title="Документ с файлами",
        document_type="memo",
        category=category,
        author=employee,
        department=child_department,
    )


class TestDocumentFileUpload:
    def test_upload_and_list(self, employee_client, document):
        response = employee_client.post(
            f"/api/documents/{document.id}/files/",
            {"file": upload()},
            format="multipart",
        )

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["original_name"] == "report.pdf"
        assert data["file_type"] == "pdf"
        assert data["mime_type"] == "application/pdf"
        assert data["is_main"] is True

        listed = employee_client.get(f"/api/documents/{document.id}/files/")
        assert listed.status_code == 200
        assert listed.json()["data"]["count"] == 1

    def test_storage_name_is_generated(self, employee_client, document):
        employee_client.post(
            f"/api/documents/{document.id}/files/",
            {"file": upload("private-report.pdf")},
            format="multipart",
        )
        document_file = DocumentFile.objects.get()
        stored_name = Path(document_file.file.name).name
        assert stored_name != "private-report.pdf"
        assert stored_name.endswith(".pdf")
        assert len(Path(stored_name).stem) == 32

    def test_new_main_file_replaces_previous_main(self, employee_client, document):
        employee_client.post(
            f"/api/documents/{document.id}/files/",
            {"file": upload("first.pdf")},
            format="multipart",
        )
        employee_client.post(
            f"/api/documents/{document.id}/files/",
            {"file": upload("second.pdf"), "is_main": True},
            format="multipart",
        )
        assert DocumentFile.objects.filter(document=document, is_main=True).count() == 1
        assert DocumentFile.objects.get(is_main=True).original_name == "second.pdf"

    @pytest.mark.parametrize(
        ("name", "mime"),
        [
            ("virus.exe", "application/x-msdownload"),
            ("image.jpg", "application/pdf"),
        ],
    )
    def test_invalid_extension_or_mime_rejected(
        self, employee_client, document, name, mime
    ):
        response = employee_client.post(
            f"/api/documents/{document.id}/files/",
            {"file": upload(name, mime=mime)},
            format="multipart",
        )
        assert response.status_code == 400
        assert not DocumentFile.objects.exists()

    def test_oversized_file_rejected(self, employee_client, document):
        response = employee_client.post(
            f"/api/documents/{document.id}/files/",
            {"file": upload(content=b"x" * 1025)},
            format="multipart",
        )
        assert response.status_code == 400

    def test_executable_disguised_as_pdf_rejected(self, employee_client, document):
        response = employee_client.post(
            f"/api/documents/{document.id}/files/",
            {"file": upload(content=b"MZ executable")},
            format="multipart",
        )
        assert response.status_code == 400

    def test_files_locked_after_submit(self, employee_client, document):
        employee_client.post(f"/api/documents/{document.id}/submit/")
        response = employee_client.post(
            f"/api/documents/{document.id}/files/",
            {"file": upload()},
            format="multipart",
        )
        assert response.status_code == 400


class TestDocumentFileDownloadAndDelete:
    @pytest.fixture
    def document_file(self, employee_client, document):
        employee_client.post(
            f"/api/documents/{document.id}/files/",
            {"file": upload(content=b"%PDF-download me")},
            format="multipart",
        )
        return DocumentFile.objects.get()

    def test_download(self, employee_client, document_file):
        response = employee_client.get(
            f"/api/document-files/{document_file.id}/download/"
        )
        assert response.status_code == 200
        assert b"".join(response.streaming_content) == b"%PDF-download me"
        assert "report.pdf" in response["Content-Disposition"]

    def test_unrelated_employee_cannot_download(
        self, auth_client, user_factory, child_department, document_file
    ):
        other = user_factory(department=child_department)
        response = auth_client(other).get(
            f"/api/document-files/{document_file.id}/download/"
        )
        assert response.status_code == 404

    def test_delete_removes_database_and_storage_file(
        self,
        employee_client,
        document_file,
        django_capture_on_commit_callbacks,
    ):
        stored_path = Path(document_file.file.path)
        assert stored_path.exists()
        with django_capture_on_commit_callbacks(execute=True):
            response = employee_client.delete(f"/api/document-files/{document_file.id}/")
        assert response.status_code == 204
        assert not DocumentFile.objects.filter(pk=document_file.pk).exists()
        assert not stored_path.exists()

    def test_delete_blocked_after_submit(self, employee_client, document, document_file):
        employee_client.post(f"/api/documents/{document.id}/submit/")
        response = employee_client.delete(f"/api/document-files/{document_file.id}/")
        assert response.status_code == 400
        assert DocumentFile.objects.filter(pk=document_file.pk).exists()
