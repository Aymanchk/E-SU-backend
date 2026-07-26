"""API организационной структуры."""

from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.constants import AuditAction
from apps.audit.services import log_action
from apps.common.permissions import HasPermissionPerAction

from .filters import DepartmentFilter
from .models import Department
from .serializers import (
    DepartmentDetailSerializer,
    DepartmentListSerializer,
    DepartmentTreeSerializer,
    DepartmentWriteSerializer,
)


@extend_schema_view(
    list=extend_schema(summary="Список подразделений", tags=["Departments"]),
    retrieve=extend_schema(summary="Подразделение", tags=["Departments"]),
    create=extend_schema(summary="Создать подразделение", tags=["Departments"]),
    partial_update=extend_schema(summary="Изменить подразделение", tags=["Departments"]),
    destroy=extend_schema(summary="Удалить подразделение", tags=["Departments"]),
)
class DepartmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasPermissionPerAction]
    permission_map = {
        "list": None,
        "retrieve": None,
        "tree": None,
        "employees": None,
        "create": "departments.manage",
        "update": "departments.manage",
        "partial_update": "departments.manage",
        "destroy": "departments.manage",
    }
    filterset_class = DepartmentFilter
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["name"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return Department.objects.select_related("parent", "manager").annotate(
            employees_count=Count(
                "employees", filter=Q(employees__is_deleted=False), distinct=True
            ),
            children_count=Count("children", filter=Q(children__is_deleted=False), distinct=True),
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return DepartmentWriteSerializer
        if self.action == "retrieve":
            return DepartmentDetailSerializer
        return DepartmentListSerializer

    def perform_create(self, serializer):
        department = serializer.save(created_by=self.request.user, updated_by=self.request.user)
        log_action(
            self.request,
            action=AuditAction.DEPARTMENT_CREATE,
            obj=department,
            description=f"Создано подразделение {department.name}",
        )

    def perform_update(self, serializer):
        department = serializer.save(updated_by=self.request.user)
        log_action(
            self.request,
            action=AuditAction.DEPARTMENT_UPDATE,
            obj=department,
            description=f"Изменено подразделение {department.name}",
            metadata={"fields": list(self.request.data.keys())},
        )

    def perform_destroy(self, instance):
        """
        ТЗ: нельзя удалить подразделение, если к нему привязаны
        активные пользователи или документы. В этом случае деактивация.
        """
        active_employees = instance.employees.filter(is_deleted=False).count()
        if active_employees:
            raise serializers.ValidationError(
                f"Нельзя удалить подразделение: к нему привязано "
                f"{active_employees} сотрудников. Используйте деактивацию."
            )

        children = instance.children.filter(is_deleted=False).count()
        if children:
            raise serializers.ValidationError(
                f"Нельзя удалить подразделение: у него {children} дочерних. "
                f"Сначала перенесите или удалите их."
            )

        # Здесь же в ТЗ №2 добавится проверка на документы

        log_action(
            self.request,
            action=AuditAction.DEPARTMENT_DELETE,
            obj=instance,
            description=f"Удалено подразделение {instance.name}",
        )
        instance.delete()

    @extend_schema(
        summary="Дерево подразделений",
        description="Возвращает вложенную структуру подразделений.",
        tags=["Departments"],
        responses={200: DepartmentTreeSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="tree", pagination_class=None)
    def tree(self, request):
        departments = list(Department.objects.select_related("manager").order_by("name"))

        nodes = {}
        for department in departments:
            data = DepartmentTreeSerializer(department).data
            data["children"] = []
            nodes[department.id] = data

        roots = []
        for department in departments:
            node = nodes[department.id]
            parent_id = department.parent_id
            if parent_id and parent_id in nodes:
                nodes[parent_id]["children"].append(node)
            else:
                roots.append(node)

        return Response(roots)

    @extend_schema(
        summary="Сотрудники подразделения",
        tags=["Departments"],
    )
    @action(detail=True, methods=["get"], url_path="employees")
    def employees(self, request, pk=None):
        from apps.accounts.models import User
        from apps.accounts.serializers import UserListSerializer

        department = self.get_object()

        include_children = request.query_params.get("include_children") == "true"
        if include_children:
            department_ids = [department.id] + [d.id for d in department.get_descendants()]
            queryset = User.objects.filter(department_id__in=department_ids)
        else:
            queryset = User.objects.filter(department=department)

        queryset = queryset.select_related("role", "department").order_by("last_name", "first_name")

        page = self.paginate_queryset(queryset)
        serializer = UserListSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)
