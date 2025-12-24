from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, District, Position, EventImportance, Event, Participation


# Регистрация кастомной модели пользователя
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'district', 'position')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'district', 'position')

    fieldsets = UserAdmin.fieldsets + (
        ('Дополнительная информация', {
            'fields': (
                'middle_name',
                'district',
                'position',
            )
        }),
    )


# === РАЙОНЫ — с ограничением на редактирование team_photo ===
@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'team_photo')
    search_fields = ('name', 'code')

    # Поля для редактирования
    fields = ('name', 'code', 'team_photo')

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Если пользователь не руководитель своего района — делаем поле team_photo только для чтения
        if obj:  # obj — это редактируемый район
            is_leader = (
                request.user.is_authenticated and
                request.user.district == obj and
                request.user.position and
                "руководитель" in request.user.position.title.lower()
            )
            if not is_leader:
                form.base_fields['team_photo'].disabled = True
                form.base_fields['team_photo'].help_text = "Только Руководитель отделения может редактировать фото команды."
        return form

    def has_change_permission(self, request, obj=None):
        # Разрешаем редактировать район только если пользователь — Руководитель этого района
        # (или суперадмин)
        if obj and request.user.is_authenticated:
            if request.user.is_superuser:
                return True
            if request.user.district == obj and request.user.position and "руководитель" in request.user.position.title.lower():
                return True
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Никто не может удалять районы (на всякий случай)
        return False


# === Остальные модели без изменений ===
@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('title', 'description')
    search_fields = ('title',)


@admin.register(EventImportance)
class EventImportanceAdmin(admin.ModelAdmin):
    list_display = ('level', 'weight')
    search_fields = ('level',)
    ordering = ('-weight',)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'event_type', 'importance', 'participants_count')
    list_filter = ('event_type', 'importance', 'date')
    search_fields = ('name',)


@admin.register(Participation)
class ParticipationAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'role', 'status')
    list_filter = ('role', 'status')
    search_fields = ('user__username', 'event__name')