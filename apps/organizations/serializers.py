"""Сериализаторы организационной структуры."""

from rest_framework import serializers

from .models import Department


class DepartmentShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "code", "name", "status"]


class ManagerShortSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    position = serializers.CharField(read_only=True)


class DepartmentListSerializer(serializers.ModelSerializer):
    manager = ManagerShortSerializer(read_only=True)
    parent = DepartmentShortSerializer(read_only=True)
    employees_count = serializers.IntegerField(read_only=True)
    children_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Department
        fields = [
            "id",
            "name",
            "code",
            "description",
            "parent",
            "manager",
            "status",
            "employees_count",
            "children_count",
            "created_at",
            "updated_at",
        ]


class DepartmentDetailSerializer(DepartmentListSerializer):
    ancestors = serializers.SerializerMethodField()

    class Meta(DepartmentListSerializer.Meta):
        fields = DepartmentListSerializer.Meta.fields + ["ancestors"]

    def get_ancestors(self, obj) -> list:
        return DepartmentShortSerializer(obj.get_ancestors(), many=True).data


class DepartmentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = [
            "id",
            "name",
            "code",
            "description",
            "parent",
            "manager",
            "status",
        ]

    def validate_code(self, value):
        qs = Department.all_objects.filter(code=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Подразделение с таким кодом уже существует")
        return value

    def validate(self, attrs):
        parent = attrs.get("parent")
        instance = self.instance

        if parent is not None and instance is not None:
            if parent.pk == instance.pk:
                raise serializers.ValidationError(
                    {"parent": "Подразделение не может быть своим родителем"}
                )
            # проверка на цикл: нельзя сделать родителем своего потомка
            node = parent
            visited = set()
            while node is not None:
                if node.pk == instance.pk:
                    raise serializers.ValidationError(
                        {"parent": "Нельзя выбрать родителем дочернее подразделение"}
                    )
                if node.pk in visited:
                    break
                visited.add(node.pk)
                node = node.parent

        return attrs


class DepartmentTreeSerializer(serializers.ModelSerializer):
    """
    Узел дерева. Поле children заполняется вручную во вьюхе (перезаписывается
    после сериализации), поэтому здесь не читаем реальный related manager
    Department.children, а просто отдаём заглушку.
    """

    children = serializers.SerializerMethodField()
    manager = ManagerShortSerializer(read_only=True)

    class Meta:
        model = Department
        fields = ["id", "name", "code", "status", "manager", "children"]

    def get_children(self, obj) -> list:
        return []
