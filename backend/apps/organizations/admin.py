from django.contrib import admin

from .models import Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "parent", "manager", "status", "employees_count")
    list_filter = ("status", "parent")
    search_fields = ("name", "code")
    autocomplete_fields = ["parent", "manager"]
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")

    @admin.display(description="Сотрудников")
    def employees_count(self, obj):
        return obj.employees.count()
