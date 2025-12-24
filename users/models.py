from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


# --- СПРАВОЧНЫЕ МОДЕЛИ (LOOKUP TABLES) ---

class District(models.Model):
    """
    Справочник районов
    """
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Название района"))
    code = models.CharField(
        max_length=10,
        unique=True,
        verbose_name=_("Код района"),
        help_text=_("Краткий код или аббревиатура")
    )

    team_photo = models.ImageField(
        upload_to='district_teams/',
        null=True,
        blank=True,
        verbose_name=_("Фотография команды района")
    )

    class Meta:
        verbose_name = _("Район")
        verbose_name_plural = _("Районы")

    def __str__(self):
        return self.name


class Position(models.Model):
    """
    Справочник должностей
    """
    title = models.CharField(max_length=100, unique=True, verbose_name=_("Название должности"))
    description = models.TextField(blank=True, verbose_name=_("Описание и обязанности"))

    class Meta:
        verbose_name = _("Должность")
        verbose_name_plural = _("Должности")

    def __str__(self):
        return self.title


class EventImportance(models.Model):
    """
    Справочник уровней важности мероприятий
    """
    level = models.CharField(max_length=50, unique=True, verbose_name=_("Уровень важности"))
    weight = models.IntegerField(
        unique=True,
        verbose_name=_("Вес"),
        help_text=_("Числовой вес для сортировки (например, 1 — низкий, 5 — высокий)")
    )

    class Meta:
        verbose_name = _("Важность мероприятия")
        verbose_name_plural = _("Важность мероприятий")
        ordering = ['-weight']

    def __str__(self):
        return self.level


# --- МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ ---

class CustomUser(AbstractUser):
    """
    Актуальная модель пользователя под текущую систему (декабрь 2025)
    """
    DEPARTMENT_TYPE_CHOICES = [
        ('apparat', _('Аппарат')),
        ('district', _('Районное отделение')),
    ]

    # ФИО
    middle_name = models.CharField(max_length=150, blank=True, verbose_name=_("Отчество"))

    # Email — для уведомлений и восстановления пароля
    email = models.EmailField(
        _("Адрес электронной почты"),
        max_length=254,
        blank=True,
        help_text=_("Будет использоваться для уведомлений и восстановления пароля")
    )

    # Тип отдела — ключевое поле для логики регистрации
    department_type = models.CharField(
        max_length=20,
        choices=DEPARTMENT_TYPE_CHOICES,
        blank=True,
        null=True,
        verbose_name=_("Тип отдела")
    )

    telegram_id = models.BigIntegerField(
        'Telegram ID',
        null=True,
        blank=True,
        unique=True,
        help_text='ID пользователя в Telegram для авторизации в боте'
    )

    # Поля для районных отделений
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name=_("Район")
    )
    position = models.ForeignKey(
        Position,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name=_("Должность")
    )

    # Опционально: аватарка
    avatar = models.ImageField(
        upload_to='avatars/',
        null=True,
        blank=True,
        verbose_name="Аватар"
    )

    def get_avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return '/static/default_avatar.jpg'

    # Методы для красивого отображения ФИО
    def get_full_name_official(self):
        """Фамилия Имя Отчество"""
        parts = [self.last_name, self.first_name, self.middle_name]
        return ' '.join(filter(None, parts)).strip()

    def get_short_name_official(self):
        """Фамилия И. О."""
        short_parts = [self.last_name]
        if self.first_name:
            short_parts.append(f'{self.first_name[0].upper()}.')
        if self.middle_name:
            short_parts.append(f'{self.middle_name[0].upper()}.')
        return ' '.join(short_parts)

    class Meta:
        verbose_name = _("Пользователь")
        verbose_name_plural = _("Пользователи")

    def __str__(self):
        return self.get_full_name_official() or self.username


# --- МОДЕЛИ МЕРОПРИЯТИЙ (ДЛЯ ОТЧЕТОВ) ---

class Event(models.Model):
    EVENT_TYPE_CHOICES = [
        ('official', _('Официальное мероприятие')),
        ('organized', _('Организованное районное мероприятие')),
    ]

    name = models.CharField(max_length=255, verbose_name=_("Название мероприятия"))
    date = models.DateField(verbose_name=_("Дата проведения"))
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
        default='official',
        verbose_name=_("Тип мероприятия")
    )
    importance = models.ForeignKey(
        EventImportance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events',
        verbose_name=_("Важность")
    )
    participants_count = models.IntegerField(default=0, verbose_name=_("Количество участников"))

    class Meta:
        verbose_name = _("Мероприятие")
        verbose_name_plural = _("Мероприятия")
        ordering = ['-date']

    def __str__(self):
        return self.name


class Participation(models.Model):
    ROLE_CHOICES = [
        ('delegate', _('Делегат')),
        ('volunteer', _('Волонтёр')),
        ('listener', _('Слушатель')),
        ('organizer', _('Организатор')),
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='event_participations',
        verbose_name=_("Пользователь")
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='participations',
        verbose_name=_("Мероприятие")
    )
    role = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        default='listener',
        verbose_name=_("Роль")
    )
    status = models.CharField(
        max_length=50,
        default=_('Завершено'),
        verbose_name=_("Статус участия")
    )

    class Meta:
        verbose_name = _("Участие")
        verbose_name_plural = _("Участия")
        unique_together = ('user', 'event')

    def __str__(self):
        return f"{self.get_role_display()} в {self.event.name} (User: {self.user.username})"