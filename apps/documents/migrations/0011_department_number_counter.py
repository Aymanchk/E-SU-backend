import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0010_approval_route_source_snapshot"),
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="documentnumbercounter",
            name="unique_document_counter_category_year",
        ),
        migrations.AddField(
            model_name="documentnumbercounter",
            name="department",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="document_number_counters",
                to="organizations.department",
                verbose_name="Подразделение",
            ),
        ),
        migrations.AlterField(
            model_name="documentnumbercounter",
            name="category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="number_counters",
                to="documents.documentcategory",
                verbose_name="Категория",
            ),
        ),
        migrations.AddConstraint(
            model_name="documentnumbercounter",
            constraint=models.UniqueConstraint(
                condition=models.Q(("department__isnull", False)),
                fields=("department", "year"),
                name="unique_document_counter_department_year",
            ),
        ),
    ]
