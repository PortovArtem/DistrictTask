from django.db import models
from django.utils import timezone


class Task(models.Model):
    TYPE_CHOICES = [
        ('mobilization', 'Мобилизация'),
        ('regional', 'Региональная'),
        ('district', 'Районная'),
        ('online', 'Онлайн задача'),
        ('help', 'Помощь'),
    ]

    STATUS_CHOICES = [
        ('open', 'Открыта'),
        ('in_progress', 'В работе'),
        ('done', 'Выполнена'),
        ('archived', 'Архивирована'),
    ]

    # Основные поля
    title = models.CharField(max_length=255, verbose_name="Заголовок")
    description = models.TextField(verbose_name="Описание задачи")

    # Даты
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    deadline = models.DateField(verbose_name="Дедлайн")
    deadline_time = models.TimeField(verbose_name="Время дедлайна", null=True, blank=True)

    event_date = models.DateField(verbose_name="Дата проведения", null=True, blank=True)
    event_time = models.TimeField(verbose_name="Время проведения", null=True, blank=True)

    users_signed_up = models.ManyToManyField(
        'users.CustomUser',
        related_name='signed_up_tasks',
        blank=True,
        verbose_name="Записавшиеся пользователи"
    )


    # Тип и статус
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='district',
        verbose_name="Тип задачи"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open',
        verbose_name="Статус"
    )

    # Привязка к району
    district = models.ForeignKey(
        'users.District',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Район"
    )

    # Метаданные от бота
    created_by_username = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        verbose_name="Создана (имя пользователя ТГ)"
    )
    created_by_user_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="Создана (ID пользователя ТГ)"
    )

    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"
        ordering = ['-deadline', '-created_at']
        indexes = [
            models.Index(fields=['deadline']),
            models.Index(fields=['type']),
            models.Index(fields=['district']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_type_display()})"

    # --- ИСПРАВЛЕННЫЕ BOOLEAN-СВОЙСТВА ---
    def is_active(self):
        """Актуальна ли задача (дедлайн не прошёл)"""
        return self.deadline >= timezone.now().date()

    is_active.boolean = True
    is_active.short_description = 'Активна'

    def get_signed_up_count_in_district(self, district):
        """Количество записавшихся из конкретного района"""
        if district is None:
            return 0
        return self.users_signed_up.filter(district=district).count()

    def get_signed_up_users_in_district(self, district):
        """Список записавшихся из конкретного района"""
        if district is None:
            return self.users_signed_up.none()
        return self.users_signed_up.filter(district=district)


    def is_overdue(self):
        """Просрочена ли задача"""
        return self.deadline < timezone.now().date() and self.status != 'done'

    is_overdue.boolean = True
    is_overdue.short_description = 'Просрочена'