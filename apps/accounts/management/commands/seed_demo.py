"""Создать полный набор демонстрационных данных для ручной проверки и работы E-SU."""

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Permission, Role, RolePermission, User, UserStatus
from apps.common.models import SystemSetting
from apps.documents.models import (
    ApprovalAction,
    ApprovalActionType,
    ApprovalRoute,
    ApprovalRouteSource,
    ApprovalRouteStatus,
    ApprovalRouteTemplate,
    ApprovalRouteTemplateStep,
    ApprovalStep,
    ApprovalStepStatus,
    ApprovalTemplateApproverType,
    Document,
    DocumentCategory,
    DocumentCategoryStatus,
    DocumentComment,
    DocumentCommentType,
    DocumentHistory,
    DocumentHistoryAction,
    DocumentPriority,
    DocumentStatus,
)
from apps.notifications.models import Notification, NotificationType
from apps.organizations.models import Department, DepartmentStatus


class Command(BaseCommand):
    help = "Создать полный набор демонстрационных данных (роли, отделы, пользователи, категории, документы, уведомления)"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Генерация демонстрационных данных E-SU ==="))

        # -------------------------------------------------------------------
        # 1. Права и роли
        # -------------------------------------------------------------------
        permissions_data = [
            ("documents.view", "Просмотр документов", "documents"),
            ("documents.create", "Создание документов", "documents"),
            ("documents.edit", "Редактирование документов", "documents"),
            ("documents.approve", "Согласование документов", "documents"),
            ("documents.return", "Возврат документов на доработку", "documents"),
            ("documents.archive", "Архивирование документов", "documents"),
            ("users.manage", "Управление пользователями", "users"),
            ("departments.manage", "Управление подразделениями", "departments"),
            ("categories.manage", "Управление категориями", "categories"),
            ("audit.view", "Просмотр журнала аудита", "audit"),
            ("settings.manage", "Управление системными настройками", "settings"),
        ]
        perms_map = {}
        for code, name, group in permissions_data:
            p, _ = Permission.objects.get_or_create(
                code=code,
                defaults={"name": name, "group": group},
            )
            perms_map[code] = p

        roles_config = {
            "admin": {
                "name": "Администратор",
                "desc": "Полный доступ ко всем функциям системы",
                "perms": list(perms_map.keys()),
            },
            "manager": {
                "name": "Руководитель",
                "desc": "Согласование документов, просмотр сотрудников подразделения",
                "perms": [
                    "documents.view",
                    "documents.create",
                    "documents.edit",
                    "documents.approve",
                    "documents.return",
                ],
            },
            "office": {
                "name": "Канцелярия",
                "desc": "Регистрация, архивирование документов, справочники",
                "perms": [
                    "documents.view",
                    "documents.create",
                    "documents.edit",
                    "documents.archive",
                    "categories.manage",
                ],
            },
            "employee": {
                "name": "Сотрудник",
                "desc": "Создание и просмотр своих документов",
                "perms": ["documents.view", "documents.create"],
            },
        }

        roles = {}
        for code, r_info in roles_config.items():
            role, _ = Role.objects.get_or_create(
                code=code,
                defaults={"name": r_info["name"], "description": r_info["desc"], "is_system": True},
            )
            for p_code in r_info["perms"]:
                if p_code in perms_map:
                    RolePermission.objects.get_or_create(role=role, permission=perms_map[p_code])
            roles[code] = role

        # -------------------------------------------------------------------
        # 2. Подразделения (Оргструктура)
        # -------------------------------------------------------------------
        rectorate, _ = Department.objects.get_or_create(
            code="rectorate",
            defaults={"name": "Ректорат", "status": DepartmentStatus.ACTIVE, "description": "Руководство университета"},
        )
        it_dept, _ = Department.objects.get_or_create(
            code="it",
            defaults={"name": "IT департамент", "parent": rectorate, "status": DepartmentStatus.ACTIVE, "description": "Отдел цифровых технологий и инфраструктуры"},
        )
        accounting, _ = Department.objects.get_or_create(
            code="accounting",
            defaults={"name": "Финансовый отдел", "parent": rectorate, "status": DepartmentStatus.ACTIVE, "description": "Бухгалтерия и финансовый учет"},
        )
        hr_dept, _ = Department.objects.get_or_create(
            code="hr",
            defaults={"name": "Отдел кадров", "parent": rectorate, "status": DepartmentStatus.ACTIVE, "description": "Управление персоналом"},
        )
        edu_dept, _ = Department.objects.get_or_create(
            code="edu",
            defaults={"name": "Учебный отдел", "parent": rectorate, "status": DepartmentStatus.ACTIVE, "description": "Организация учебного процесса"},
        )
        chancellery, _ = Department.objects.get_or_create(
            code="chancellery",
            defaults={"name": "Канцелярия", "parent": rectorate, "status": DepartmentStatus.ACTIVE, "description": "Общий документооборот и архив"},
        )

        # -------------------------------------------------------------------
        # 3. Пользователи
        # -------------------------------------------------------------------
        default_password = "DemoPass123!"

        demo_users_data = [
            ("admin@esu.kg", "Садыкова", "Айдана", "Алиевна", "admin", rectorate, "Главный администратор системы", True, True),
            ("rector@esu.kg", "Токтосунов", "Бекжан", "Асанович", "manager", rectorate, "Ректор университета", False, False),
            ("manager@esu.kg", "Руководителев", "Пётр", "Сергеевич", "manager", it_dept, "Руководитель IT департамента", False, False),
            ("office@esu.kg", "Канцелярова", "Анна", "Владимировна", "office", chancellery, "Специалист канцелярии", False, False),
            ("employee@esu.kg", "Сотрудников", "Иван", "Дмитриевич", "employee", it_dept, "Ведущий разработчик", False, False),
            ("buh@esu.kg", "Бухгалтерова", "Мария", "Ивановна", "manager", accounting, "Главный бухгалтер", False, False),
            ("hr@esu.kg", "Кадрова", "Елена", "Павловна", "employee", hr_dept, "Специалист по кадрам", False, False),
            ("teacher@esu.kg", "Алиев", "Нурбек", "Кубанычбекович", "employee", edu_dept, "Старший преподаватель", False, False),
        ]

        users = {}
        for email, last_name, first_name, middle_name, role_code, dept, pos, is_staff, is_superuser in demo_users_data:
            user = User.all_objects.filter(email=email).first()
            if not user:
                user = User.objects.create_user(
                    email=email,
                    password=default_password,
                    first_name=first_name,
                    last_name=last_name,
                    middle_name=middle_name,
                    role=roles.get(role_code),
                    department=dept,
                    position=pos,
                    status=UserStatus.ACTIVE,
                    is_active=True,
                    is_staff=is_staff,
                    is_superuser=is_superuser,
                )
                self.stdout.write(self.style.SUCCESS(f"  + Создан пользователь: {user.email} ({role_code})"))
            else:
                user.role = roles.get(role_code)
                user.department = dept
                user.position = pos
                user.status = UserStatus.ACTIVE
                user.is_active = True
                user.is_staff = is_staff
                user.is_superuser = is_superuser
                user.set_password(default_password)
                user.save()
            users[email] = user

        # Назначаем руководителей подразделений
        rectorate.manager = users["rector@esu.kg"]
        rectorate.save(update_fields=["manager"])
        it_dept.manager = users["manager@esu.kg"]
        it_dept.save(update_fields=["manager"])
        accounting.manager = users["buh@esu.kg"]
        accounting.save(update_fields=["manager"])
        chancellery.manager = users["office@esu.kg"]
        chancellery.save(update_fields=["manager"])

        # -------------------------------------------------------------------
        # 4. Категории документов
        # -------------------------------------------------------------------
        categories_data = [
            ("order", "Приказ", 1825, "Официальные распорядительные документы ректората"),
            ("contract", "Договор", 1095, "Договоры поставки, подряда и соглашения"),
            ("memo", "Служебная записка", 365, "Внутренняя служебная переписка между отделами"),
            ("request", "Заявка", 365, "Заявки на закупку, доступ к сервисам и ресурсы"),
            ("act", "Акт", 730, "Акты приёмки-передачи, сверок и инвентаризации"),
            ("regulation", "Положение", 3650, "Внутренние регламенты и стандарты университета"),
        ]

        categories = {}
        for code, name, ret_days, desc in categories_data:
            cat, _ = DocumentCategory.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "retention_period_days": ret_days,
                    "description": desc,
                    "requires_file": False,
                    "status": DocumentCategoryStatus.ACTIVE,
                },
            )
            categories[code] = cat

        # -------------------------------------------------------------------
        # 5. Шаблоны маршрутов согласования
        # -------------------------------------------------------------------
        # Шаблон для приказов
        order_tpl, _ = ApprovalRouteTemplate.objects.get_or_create(
            category=categories["order"],
            name="Стандартный маршрут приказа",
            defaults={"is_active": True},
        )
        ApprovalRouteTemplateStep.objects.get_or_create(
            template=order_tpl,
            order=1,
            defaults={"approver_type": ApprovalTemplateApproverType.DEPARTMENT_MANAGER, "is_required": True},
        )
        ApprovalRouteTemplateStep.objects.get_or_create(
            template=order_tpl,
            order=2,
            defaults={"approver_type": ApprovalTemplateApproverType.ROLE, "role": roles["office"], "is_required": True},
        )
        ApprovalRouteTemplateStep.objects.get_or_create(
            template=order_tpl,
            order=3,
            defaults={"approver_type": ApprovalTemplateApproverType.SPECIFIC_USER, "specific_user": users["rector@esu.kg"], "is_required": True},
        )

        # Шаблон для служебных записок
        memo_tpl, _ = ApprovalRouteTemplate.objects.get_or_create(
            category=categories["memo"],
            name="Согласование служебной записки",
            defaults={"is_active": True},
        )
        ApprovalRouteTemplateStep.objects.get_or_create(
            template=memo_tpl,
            order=1,
            defaults={"approver_type": ApprovalTemplateApproverType.DEPARTMENT_MANAGER, "is_required": True},
        )

        # Шаблон для договоров
        contract_tpl, _ = ApprovalRouteTemplate.objects.get_or_create(
            category=categories["contract"],
            name="Согласование финансового договора",
            defaults={"is_active": True},
        )
        ApprovalRouteTemplateStep.objects.get_or_create(
            template=contract_tpl,
            order=1,
            defaults={"approver_type": ApprovalTemplateApproverType.SPECIFIC_USER, "specific_user": users["buh@esu.kg"], "is_required": True},
        )
        ApprovalRouteTemplateStep.objects.get_or_create(
            template=contract_tpl,
            order=2,
            defaults={"approver_type": ApprovalTemplateApproverType.ROLE, "role": roles["manager"], "is_required": True},
        )
        ApprovalRouteTemplateStep.objects.get_or_create(
            template=contract_tpl,
            order=3,
            defaults={"approver_type": ApprovalTemplateApproverType.SPECIFIC_USER, "specific_user": users["rector@esu.kg"], "is_required": True},
        )

        # -------------------------------------------------------------------
        # 6. Демо-документы различных статусов
        # -------------------------------------------------------------------
        now = timezone.now()

        # Документ 1: Согласован (APPROVED)
        doc1, created = Document.objects.get_or_create(
            registration_number="ESU-ORD-2026-000001",
            defaults={
                "title": "Приказ о начале учебного года и графике экзаменационных сессий",
                "description": "Утверждение графика учебного процесса на 2026/2027 учебный год для всех факультетов.",
                "document_type": "order",
                "category": categories["order"],
                "author": users["admin@esu.kg"],
                "department": rectorate,
                "responsible": users["admin@esu.kg"],
                "priority": DocumentPriority.HIGH,
                "status": DocumentStatus.APPROVED,
                "submitted_at": now - timedelta(days=12),
                "approved_at": now - timedelta(days=2),
                "current_approval_step": 3,
            },
        )
        if created:
            route1 = ApprovalRoute.objects.create(
                document=doc1,
                status=ApprovalRouteStatus.COMPLETED,
                source=ApprovalRouteSource.CATEGORY_TEMPLATE,
                template=order_tpl,
                created_by=users["admin@esu.kg"],
                completed_at=now - timedelta(days=2),
            )
            ApprovalStep.objects.create(
                route=route1,
                document=doc1,
                order=1,
                approver=users["rector@esu.kg"],
                role=roles["manager"],
                status=ApprovalStepStatus.APPROVED,
                acted_at=now - timedelta(days=10),
                comment="Согласовано без замечаний",
            )
            ApprovalStep.objects.create(
                route=route1,
                document=doc1,
                order=2,
                approver=users["office@esu.kg"],
                role=roles["office"],
                status=ApprovalStepStatus.APPROVED,
                acted_at=now - timedelta(days=5),
                comment="Зарегистрировано в журнале приказов",
            )
            DocumentHistory.objects.create(
                document=doc1,
                user=users["admin@esu.kg"],
                action=DocumentHistoryAction.APPROVED,
                description="Документ полностью утверждён и вступил в силу",
            )

        # Документ 2: На согласовании (IN_REVIEW)
        doc2, created = Document.objects.get_or_create(
            registration_number="ESU-AGR-2026-000002",
            defaults={
                "title": "Договор на поставку серверного оборудования для дата-центра",
                "description": "Закупка высокопроизводительных серверов для расширения вычислительного кластера.",
                "document_type": "contract",
                "category": categories["contract"],
                "author": users["employee@esu.kg"],
                "department": it_dept,
                "responsible": users["manager@esu.kg"],
                "priority": DocumentPriority.URGENT,
                "status": DocumentStatus.IN_REVIEW,
                "deadline": now + timedelta(days=5),
                "submitted_at": now - timedelta(days=2),
                "current_approval_step": 2,
            },
        )
        if created:
            route2 = ApprovalRoute.objects.create(
                document=doc2,
                status=ApprovalRouteStatus.ACTIVE,
                source=ApprovalRouteSource.CATEGORY_TEMPLATE,
                template=contract_tpl,
                created_by=users["employee@esu.kg"],
            )
            step1 = ApprovalStep.objects.create(
                route=route2,
                document=doc2,
                order=1,
                approver=users["buh@esu.kg"],
                role=roles["manager"],
                status=ApprovalStepStatus.APPROVED,
                acted_at=now - timedelta(days=1),
                comment="Бюджет согласован по статье 4.1",
            )
            ApprovalAction.objects.create(
                document=doc2,
                step=step1,
                actor=users["buh@esu.kg"],
                action=ApprovalActionType.APPROVE,
                comment="Бюджет согласован по статье 4.1",
            )
            ApprovalStep.objects.create(
                route=route2,
                document=doc2,
                order=2,
                approver=users["manager@esu.kg"],
                role=roles["manager"],
                status=ApprovalStepStatus.CURRENT,
            )
            ApprovalStep.objects.create(
                route=route2,
                document=doc2,
                order=3,
                approver=users["rector@esu.kg"],
                role=roles["manager"],
                status=ApprovalStepStatus.PENDING,
            )
            DocumentComment.objects.create(
                document=doc2,
                author=users["buh@esu.kg"],
                comment_type=DocumentCommentType.APPROVAL,
                text="Смета проверена, финансирование выделено в полном объёме.",
            )

        # Документ 3: На согласовании (IN_REVIEW) - служебная записка
        doc3, created = Document.objects.get_or_create(
            registration_number="ESU-MEMO-2026-000003",
            defaults={
                "title": "Служебная записка о выделении средств на продление лицензий ПО",
                "description": "Продление подписки на средства разработки и аналитики для лаборатории ИИ.",
                "document_type": "memo",
                "category": categories["memo"],
                "author": users["employee@esu.kg"],
                "department": it_dept,
                "responsible": users["employee@esu.kg"],
                "priority": DocumentPriority.NORMAL,
                "status": DocumentStatus.IN_REVIEW,
                "deadline": now + timedelta(days=3),
                "submitted_at": now - timedelta(hours=14),
                "current_approval_step": 1,
            },
        )
        if created:
            route3 = ApprovalRoute.objects.create(
                document=doc3,
                status=ApprovalRouteStatus.ACTIVE,
                source=ApprovalRouteSource.CATEGORY_TEMPLATE,
                template=memo_tpl,
                created_by=users["employee@esu.kg"],
            )
            ApprovalStep.objects.create(
                route=route3,
                document=doc3,
                order=1,
                approver=users["manager@esu.kg"],
                role=roles["manager"],
                status=ApprovalStepStatus.CURRENT,
            )

        # Документ 4: Завершён (COMPLETED)
        doc4, _ = Document.objects.get_or_create(
            registration_number="ESU-REQ-2026-000004",
            defaults={
                "title": "Заявка на подключение дополнительного сетевого оборудования",
                "description": "Установка Wi-Fi роутеров в учебном корпусе №3, аудитории 301-308.",
                "document_type": "request",
                "category": categories["request"],
                "author": users["teacher@esu.kg"],
                "department": edu_dept,
                "responsible": users["employee@esu.kg"],
                "priority": DocumentPriority.NORMAL,
                "status": DocumentStatus.COMPLETED,
                "submitted_at": now - timedelta(days=20),
                "completed_at": now - timedelta(days=4),
            },
        )

        # Документ 5: Черновик (DRAFT)
        doc5, _ = Document.objects.get_or_create(
            title="Черновик регламента внутреннего электронного документооборота",
            defaults={
                "description": "Проект правил оформления и согласования документов в системе E-SU.",
                "document_type": "regulation",
                "category": categories["regulation"],
                "author": users["office@esu.kg"],
                "department": chancellery,
                "responsible": users["office@esu.kg"],
                "priority": DocumentPriority.LOW,
                "status": DocumentStatus.DRAFT,
            },
        )

        # Документ 6: Возвращён на доработку (RETURNED)
        doc6, created = Document.objects.get_or_create(
            registration_number="ESU-ACT-2026-000005",
            defaults={
                "title": "Акт сверки взаиморасчетов за II квартал 2026 года",
                "description": "Акт сверки с поставщиком телекоммуникационных услуг.",
                "document_type": "act",
                "category": categories["act"],
                "author": users["buh@esu.kg"],
                "department": accounting,
                "responsible": users["buh@esu.kg"],
                "priority": DocumentPriority.HIGH,
                "status": DocumentStatus.RETURNED,
                "submitted_at": now - timedelta(days=6),
            },
        )
        if created:
            DocumentComment.objects.create(
                document=doc6,
                author=users["manager@esu.kg"],
                comment_type=DocumentCommentType.RETURN_REASON,
                text="Не совпадают итоговые суммы в приложении №2. Просьба перепроверить расчет НДС и переотправить.",
            )

        # Документ 7: Просрочен (OVERDUE)
        doc7, _ = Document.objects.get_or_create(
            registration_number="ESU-REQ-2026-000006",
            defaults={
                "title": "Заявка на проведение внепланового аудита серверных комнат",
                "description": "Проверка систем бесперебойного питания и пожаротушения.",
                "document_type": "request",
                "category": categories["request"],
                "author": users["employee@esu.kg"],
                "department": it_dept,
                "responsible": users["manager@esu.kg"],
                "priority": DocumentPriority.HIGH,
                "status": DocumentStatus.OVERDUE,
                "status_before_overdue": DocumentStatus.IN_REVIEW,
                "deadline": now - timedelta(days=2),
                "submitted_at": now - timedelta(days=15),
            },
        )

        # Документ 8: В архиве (ARCHIVED)
        doc8, _ = Document.objects.get_or_create(
            registration_number="ESU-AGR-2025-000088",
            defaults={
                "title": "Архивный договор аренды помещений лабораторного корпуса №2",
                "description": "Договор аренды за предыдущий период (2025 год). Срок действия истёк.",
                "document_type": "contract",
                "category": categories["contract"],
                "author": users["buh@esu.kg"],
                "department": accounting,
                "responsible": users["buh@esu.kg"],
                "priority": DocumentPriority.LOW,
                "status": DocumentStatus.ARCHIVED,
                "submitted_at": now - timedelta(days=400),
                "archived_at": now - timedelta(days=40),
            },
        )

        # -------------------------------------------------------------------
        # 7. Уведомления
        # -------------------------------------------------------------------
        Notification.objects.get_or_create(
            recipient=users["manager@esu.kg"],
            title="Требуется согласование документа",
            defaults={
                "type": NotificationType.APPROVAL_REQUIRED,
                "message": "Вам направлен на согласование документ № ESU-AGR-2026-000002 (Договор на поставку оборудования)",
                "document": doc2,
                "is_read": False,
            },
        )
        Notification.objects.get_or_create(
            recipient=users["manager@esu.kg"],
            title="Новая служебная записка",
            defaults={
                "type": NotificationType.APPROVAL_REQUIRED,
                "message": "Вам направлен на согласование документ № ESU-MEMO-2026-000003",
                "document": doc3,
                "is_read": False,
            },
        )
        Notification.objects.get_or_create(
            recipient=users["employee@esu.kg"],
            title="Документ согласован",
            defaults={
                "type": NotificationType.DOCUMENT_APPROVED,
                "message": "Приказ № ESU-ORD-2026-000001 успешно утвержден руководством",
                "document": doc1,
                "is_read": True,
                "read_at": now - timedelta(days=1),
            },
        )
        Notification.objects.get_or_create(
            recipient=users["buh@esu.kg"],
            title="Документ возвращён на доработку",
            defaults={
                "type": NotificationType.DOCUMENT_RETURNED,
                "message": "Акт № ESU-ACT-2026-000005 возвращён на доработку. Причина: Не совпадают суммы в приложении №2.",
                "document": doc6,
                "is_read": False,
            },
        )

        # -------------------------------------------------------------------
        # 8. Системные настройки
        # -------------------------------------------------------------------
        settings_defaults = [
            ("company_name", "Electronic Salymbekov University", SystemSetting.ValueType.STRING, "Название организации", True),
            ("max_file_size_mb", "25", SystemSetting.ValueType.INTEGER, "Максимальный размер загружаемого файла (МБ)", True),
            ("allowed_file_types", '["pdf", "docx", "xlsx", "jpg", "png", "zip"]', SystemSetting.ValueType.JSON, "Разрешенные расширения файлов", True),
            ("document_prefix", "ESU", SystemSetting.ValueType.STRING, "Префикс номеров документов", True),
            ("auto_archive_days", "180", SystemSetting.ValueType.INTEGER, "Срок авто-архивации завершенных документов (дней)", False),
        ]
        for key, val, val_type, desc, is_pub in settings_defaults:
            SystemSetting.objects.get_or_create(
                key=key,
                defaults={
                    "value": val,
                    "value_type": val_type,
                    "description": desc,
                    "is_public": is_pub,
                },
            )

        # -------------------------------------------------------------------
        # 9. Сводка для консоли
        # -------------------------------------------------------------------
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 70))
        self.stdout.write(self.style.SUCCESS("✓ ДЕМОНСТРАЦИОННЫЕ ДАННЫЕ УСПЕШНО СОЗДАНЫ!"))
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.WARNING(f"Единый пароль для всех демо-пользователей: {default_password}\n"))

        table_header = f"{'Email':<22} | {'Имя':<20} | {'Роль':<10} | {'Подразделение':<18}"
        self.stdout.write(self.style.HTTP_INFO(table_header))
        self.stdout.write("-" * 75)
        for email, last_name, first_name, _, role_code, dept, _, _, _ in demo_users_data:
            full_name = f"{last_name} {first_name}"
            self.stdout.write(f"{email:<22} | {full_name:<20} | {role_code:<10} | {dept.name:<18}")

        self.stdout.write("-" * 75)
        self.stdout.write(self.style.SUCCESS("\nПолезные эндпоинты API:"))
        self.stdout.write("  • Авторизация (JWT):  POST /api/v1/auth/login/")
        self.stdout.write("  • Swagger UI (доки):  GET  /api/docs/")
        self.stdout.write("  • Health check:       GET  /api/health/")
        self.stdout.write("  • Документы:          GET  /api/v1/documents/")
        self.stdout.write("  • Категории:          GET  /api/v1/document-categories/")
        self.stdout.write("  • Подразделения:      GET  /api/v1/departments/")
        self.stdout.write("  • Админка Django:     GET  /admin/ (логин: admin@esu.kg)\n")
