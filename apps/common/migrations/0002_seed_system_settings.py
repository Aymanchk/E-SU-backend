"""Начальные системные настройки."""

from django.db import migrations

SETTINGS = [
    {
        "key": "university_name",
        "value": "Салымбеков Университет",
        "value_type": "string",
        "description": "Название университета для шапки документов и писем",
        "is_public": True,
    },
    {
        "key": "sender_email",
        "value": "noreply@esu.kg",
        "value_type": "string",
        "description": "Email отправителя системных уведомлений",
        "is_public": False,
    },
    {
        "key": "allowed_file_extensions",
        "value": '["pdf", "doc", "docx", "xls", "xlsx", "jpg", "jpeg", "png"]',
        "value_type": "json",
        "description": "Допустимые расширения загружаемых файлов",
        "is_public": True,
    },
    {
        "key": "max_file_size_mb",
        "value": "20",
        "value_type": "integer",
        "description": "Максимальный размер загружаемого файла в мегабайтах",
        "is_public": True,
    },
    {
        "key": "document_number_format",
        "value": "{department_code}-{year}-{sequence:04d}",
        "value_type": "string",
        "description": "Шаблон формирования номера документа",
        "is_public": False,
    },
    {
        "key": "reminder_days_before_deadline",
        "value": "3",
        "value_type": "integer",
        "description": "За сколько дней до срока отправлять напоминание",
        "is_public": True,
    },
]


def seed(apps, schema_editor):
    SystemSetting = apps.get_model("common", "SystemSetting")
    for item in SETTINGS:
        SystemSetting.objects.update_or_create(
            key=item["key"],
            defaults={
                "value": item["value"],
                "value_type": item["value_type"],
                "description": item["description"],
                "is_public": item["is_public"],
            },
        )


def unseed(apps, schema_editor):
    SystemSetting = apps.get_model("common", "SystemSetting")
    SystemSetting.objects.filter(key__in=[s["key"] for s in SETTINGS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
