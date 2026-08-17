from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("documents", "0013_document_status_before_overdue")]

    operations = [
        migrations.AddIndex(
            model_name="document",
            index=models.Index(
                fields=["status", "deadline"], name="doc_status_deadline_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(
                fields=["status", "created_at"], name="doc_status_created_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(
                fields=["author", "created_at"], name="doc_author_created_idx"
            ),
        ),
    ]
