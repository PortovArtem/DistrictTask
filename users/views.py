from django.core.cache import cache
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.views import LoginView
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_GET
from django import forms
from django.http import Http404, HttpResponseBadRequest
import logging
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.generic import DeleteView
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.core.files.uploadedfile import InMemoryUploadedFile
from io import BytesIO
from PIL import Image
from django.contrib.auth import login
from django.db import models

from .forms import UserLoginForm, UserRegistrationForm
from .models import CustomUser, Position, District
from tasks_app.models import Task

# Настройка логгера
logger = logging.getLogger(__name__)

# --- МАКЕТНЫЕ ДАННЫЕ (MOCK DATA) ---
# (Оставил без изменений — они не зависят от модели)
MOCK_NEWS_ITEMS = [ ... ]  # твои новости
MOCK_TASKS = [ ... ]       # твои задачи
MOCK_REPORTS_DATA = { ... }  # твои отчёты


# --- ФОРМА ДЛЯ РЕДАКТИРОВАНИЯ ПРОФИЛЯ ---
class UserUpdateForm(forms.ModelForm):
    """Форма редактирования профиля — только актуальные поля"""

    class Meta:
        model = CustomUser
        fields = [
            'first_name',
            'last_name',
            'middle_name',
            'email',  # Для уведомлений
            'department_type',  # Тип отдела (если нужно редактировать)
            'position',
            'district',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'Имя'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Фамилия'}),
            'middle_name': forms.TextInput(attrs={'placeholder': 'Отчество (при наличии)'}),
            'email': forms.EmailInput(attrs={'placeholder': 'email@example.com'}),
            'avatar': forms.URLInput(attrs={'placeholder': 'https://example.com/avatar.jpg'}),
        }
        labels = {
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'middle_name': 'Отчество',
            'email': 'Email',
            'department_type': 'Тип отдела',
            'position': 'Должность',
            'district': 'Район',
        }


# --- AJAX ВЬЮХА ДЛЯ ДОЛЖНОСТЕЙ ---
@require_GET
def get_positions(request):
    district_id = request.GET.get('district_id')
    positions = Position.objects.all()

    if district_id:
        try:
            district = District.objects.get(id=district_id)
            # Ищем должность руководителя (независимо от регистра)
            head_position = Position.objects.filter(title__iexact="руководитель районного отделения").first()
            if head_position and CustomUser.objects.filter(district=district, position=head_position).exists():
                positions = positions.exclude(id=head_position.id)
        except (ValueError, District.DoesNotExist):
            pass

    return JsonResponse({
        'positions': list(positions.values('id', 'title'))
    })


# --- ПРЕДСТАВЛЕНИЯ АУТЕНТИФИКАЦИИ ---
class CustomLoginView(LoginView):
    """Страница входа"""
    template_name = 'users/login.html'
    authentication_form = UserLoginForm

    def form_valid(self, form):
        """Вызывается при успешной авторизации по логину/паролю"""
        # Сначала выполняем стандартный логин Django
        response = super().form_valid(form)

        # Проверяем, есть ли отложенный telegram_id из telegram-login
        if 'pending_telegram_id' in self.request.session:
            telegram_id = self.request.session.pop('pending_telegram_id')  # pop — чтобы удалить из сессии
            user = self.request.user
            user.telegram_id = telegram_id
            user.save(update_fields=['telegram_id'])
            messages.success(self.request, "Telegram успешно привязан к вашему аккаунту!")

        return response


class RegisterView(CreateView):
    """Страница регистрации"""
    template_name = 'users/register.html'
    form_class = UserRegistrationForm
    success_url = reverse_lazy('home')

    def form_invalid(self, form):
        """Логируем ошибки при невалидной форме"""
        logger.warning(f"Ошибка регистрации. Данные: {self.request.POST}")
        for field, errors in form.errors.items():
            logger.error(f"Поле '{field}': {', '.join(errors)}")
        return super().form_invalid(form)

    def form_valid(self, form):
        """Сохраняем и логируем успешную регистрацию"""
        try:
            user = form.save()
            logger.info(f"Успешная регистрация: {user.username} (ID: {user.pk})")
            # Автологин (раскомментируй, если нужно):
            # login(self.request, user)
            # return redirect('home')
            return super().form_valid(form)
        except Exception as e:
            logger.error(f"Ошибка при сохранении пользователя: {e}")
            form.add_error(None, "Произошла ошибка на сервере.")
            return self.form_invalid(form)


# --- СПИСОК ПОЛЬЗОВАТЕЛЕЙ ---
class UserListView(LoginRequiredMixin, ListView):
    """Список пользователей — доступ только для Руководителя и Заместителя"""
    model = CustomUser
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    login_url = 'login'

    def dispatch(self, request, *args, **kwargs):
        user = request.user

        # Проверяем, есть ли у пользователя должность
        if not user.position:
            messages.error(request, "Доступ запрещён: у вас нет должности.")
            raise Http404

        position_title = user.position.title.strip().lower()

        allowed_titles = [
            "руководитель районного отделения",
            "заместитель руководителя районного отделения",
        ]

        if position_title not in allowed_titles:
            messages.error(request, "Доступ запрещён: недостаточно прав.")
            raise Http404

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        # Показываем всех пользователей кроме себя
        return CustomUser.objects.exclude(pk=self.request.user.pk).order_by('last_name')


class UserDeleteView(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    model = CustomUser
    success_url = reverse_lazy('user_list')
    template_name = 'users/user_confirm_delete.html'  # Можно создать простой шаблон или использовать встроенный
    success_message = "Пользователь успешно удалён."

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        target_user = self.get_object()

        if not user.position or "руководитель" not in user.position.title.lower():
            messages.error(request, "Доступ запрещён: только руководитель может удалять.")
            return redirect('user_list')

        if user.district != target_user.district:
            messages.error(request, "Вы можете удалять только пользователей своего района.")
            return redirect('user_list')

        return super().dispatch(request, *args, **kwargs)


# --- РЕДАКТИРОВАНИЕ ПОЛЬЗОВАТЕЛЯ ---
class UserUpdateView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    template_name = 'users/user_edit_form.html'
    context_object_name = 'target_user'
    login_url = 'login'

    def get_object(self, queryset=None):
        """
        Для /profile/edit/ — всегда редактируем текущего пользователя.
        Для /users/<pk>/edit/ — редактируем по pk (для Руководителя).
        """
        if 'pk' in self.kwargs:
            # Руководитель редактирует другого пользователя по pk
            return super().get_object(queryset)

        # Обычный пользователь редактирует свой профиль
        return self.request.user

    def get_form_class(self):
        user = self.request.user
        target_user = self.get_object()

        # Если Руководитель редактирует пользователя своего района — полная форма
        if (user.position and
                "руководитель" in user.position.title.lower() and
                user.district == target_user.district):
            return UserUpdateForm  # Все поля

        # Обычный пользователь — только username (и аватар, если добавишь)
        class LimitedUpdateForm(forms.ModelForm):
            class Meta:
                model = CustomUser
                fields = ['username']  # Только логин (добавь 'avatar' позже)

        return LimitedUpdateForm

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if 'avatar' in form.fields:
            del form.fields['avatar']
        return form

    def get_success_url(self):
        # Руководитель → обратно в список
        if (self.request.user.position and
                "руководитель" in self.request.user.position.title.lower()):
            return reverse_lazy('user_list')

        # Обычный пользователь → в свой профиль
        return reverse_lazy('profile')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Редактирование профиля"
        return context


# --- ДАШБОРД И ДРУГИЕ СТРАНИЦЫ ---
@login_required
def home_dashboard_view(request):
    """Главная страница (дашборд)"""
    current_user = request.user

    is_leader = current_user.position and "руководитель" in current_user.position.title.lower()

    context = {
        'page_title': 'Главная',
        'user_data': request.user,
        'is_leader': is_leader,
    }
    return render(request, 'users/home_dashboard.html', context)


@login_required
def profile_view(request):
    """Страница профиля пользователя"""
    context = {
        'page_title': 'Мой Профиль',
        'user_data': request.user,
    }
    return render(request, 'users/profile_details.html', context)


@login_required
def tasks_view(request):
    page_title = 'Задачи'
    current_user = request.user

    tasks = Task.objects.all().order_by('-created_at')

    if current_user.district:
        tasks = tasks.filter(
            models.Q(district=current_user.district) |
            models.Q(district__isnull=True) |
            ~models.Q(type='district')
        )

    is_leader = current_user.position and (
        'руководитель' in current_user.position.title.lower() or
        'заместитель' in current_user.position.title.lower()
    )

    # Добавляем в каждую задачу список записавшихся из района текущего пользователя (только для лидеров)
    if is_leader and current_user.district:
        for task in tasks:
            task.signed_up_in_district = task.users_signed_up.filter(district=current_user.district)
            task.signed_up_count_in_district = task.signed_up_in_district.count()
    else:
        for task in tasks:
            task.signed_up_in_district = task.users_signed_up.none()
            task.signed_up_count_in_district = 0

    context = {
        'page_title': page_title,
        'tasks': tasks,
        'is_leader': is_leader,
    }

    return render(request, 'users/task_list.html', context)


@login_required
def task_create_view(request):
    if request.method == 'POST':
        # Здесь можно добавить логику создания задачи позже
        messages.info(request, "Создание задач через веб пока недоступно. Используйте Telegram-бот.")
        return redirect('tasks')

    # Для GET — показываем страницу с объяснением
    return render(request, 'users/task_create.html')


def telegram_login(request):
    token = request.GET.get("token")
    if not token:
        messages.error(request, "Токен отсутствует.")
        return redirect('login')

    cache_key = f"telegram_login_{token}"
    telegram_id = cache.get(cache_key)
    if not telegram_id:
        messages.error(request, "Ссылка недействительна или просрочена.")
        return redirect('login')

    if request.user.is_authenticated:
        # Уже залогинен — просто привязываем
        request.user.telegram_id = telegram_id
        request.user.save(update_fields=['telegram_id'])
        messages.success(request, "Telegram успешно привязан к вашему аккаунту!")
    else:
        # Не залогинен — ищем пользователя с таким telegram_id
        try:
            user = CustomUser.objects.get(telegram_id=telegram_id)
            login(request, user)
            messages.success(request, f"Добро пожаловать, {user.get_full_name()}!")
        except CustomUser.DoesNotExist:
            # Новый Telegram — сохраняем telegram_id в сессии и просим залогиниться
            request.session['pending_telegram_id'] = telegram_id
            messages.info(request, "Для завершения привязки Telegram войдите в аккаунт.")
            return redirect('login')

    cache.delete(cache_key)
    return redirect("home")

@login_required
def reports_view(request):
    """Страница отчётов и статистики"""
    context = {
        'page_title': 'Отчёты',
        'report_data': MOCK_REPORTS_DATA,
    }
    return render(request, 'users/report_list.html', context)


@login_required
def task_signup_toggle(request, pk):
    task = get_object_or_404(Task, pk=pk)

    if request.user in task.users_signed_up.all():
        task.users_signed_up.remove(request.user)
        messages.success(request, "Вы отменили участие в задаче.")
    else:
        task.users_signed_up.add(request.user)
        messages.success(request, "Вы успешно записались на задачу!")

    return redirect('tasks')


@login_required
def settings_view(request):
    """Страница настроек"""
    current_user = request.user

    is_leader = current_user.position and "руководитель" in current_user.position.title.lower()

    context = {
        'page_title': 'Настройки профиля',
        'is_leader': is_leader,  # ← ЭТО ОБЯЗАТЕЛЬНО ДОБАВИТЬ!
    }
    return render(request, 'users/settings.html', context)


@login_required
@csrf_exempt  # Для простоты (можно заменить на csrf_protect + проверку токена)
def upload_avatar(request):
    if request.method == 'POST' and request.FILES.get('avatar'):
        user = request.user
        user.avatar = request.FILES['avatar']
        user.save()
        return JsonResponse({'status': 'success', 'avatar_url': user.get_avatar_url()})

    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


@login_required
def upload_team_photo(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Метод не разрешён'}, status=405)

    if not request.user.position or "руководитель" not in request.user.position.title.lower():
        return JsonResponse({'status': 'error', 'message': 'Доступ запрещён'}, status=403)

    if 'team_photo' not in request.FILES:
        return JsonResponse({'status': 'error', 'message': 'Файл не выбран'}, status=400)

    original_photo = request.FILES['team_photo']

    # Открываем изображение через Pillow
    try:
        img = Image.open(original_photo)

        # Конвертируем в RGB (на случай PNG с альфа-каналом)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        # Максимальная ширина — 1920px (подойдёт для любого экрана)
        max_width = 1920
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)

        # Сохраняем в BytesIO с хорошим качеством
        output = BytesIO()
        img.save(output, format='JPEG', quality=90, optimize=True)
        output.seek(0)

        # Создаём новый файл с тем же именем
        resized_photo = InMemoryUploadedFile(
            output,
            'ImageField',
            original_photo.name.rsplit('.', 1)[0] + '.jpg',  # сохраняем как JPG
            'image/jpeg',
            output.tell(),
            None
        )

        # Сохраняем в модель
        request.user.district.team_photo = resized_photo
        request.user.district.save()

        return JsonResponse({
            'status': 'success',
            'photo_url': request.user.district.team_photo.url
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Ошибка обработки изображения'}, status=500)

