import json
import logging
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.db.models import Q
from datetime import datetime
from django.views.generic import UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect

from .models import Task
from users.models import CustomUser

logger = logging.getLogger(__name__)

@csrf_exempt
def create_task_from_telegram(request):
    """
    Эндпоинт для создания задачи из Telegram-бота.
    Защита:
    - Токен в заголовке
    - Проверка по telegram_id (привязанный пользователь)
    - Проверка должности (руководитель или заместитель)
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Ожидается метод POST.'}, status=405)

    # Защита токеном
    auth_header = request.headers.get('Authorization')
    expected_token = 'Token aB3dE9gH2jK4mN6pQ8rT1uV5wX7yZ0cF2vL9oPqRsTuVxYzAbCdEfGhIjKlMnOp'
    if auth_header != expected_token:
        logger.warning(f"Неверный токен: {auth_header}")
        return JsonResponse({'error': 'Доступ запрещён. Неверный токен.'}, status=403)

    try:
        data = json.loads(request.body)

        title = data.get('title')
        description = data.get('description')
        type_code = data.get('type')
        deadline_str = data.get('deadline')
        deadline_time_str = data.get('deadline_time')
        event_date_str = data.get('event_date')
        event_time_str = data.get('event_time')

        # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: проверка по telegram_id
        telegram_id = data.get('created_by_telegram_id')
        if not telegram_id:
            return JsonResponse({'error': 'Telegram ID отсутствует.'}, status=400)

        # Получаем пользователя по telegram_id
        try:
            creator = CustomUser.objects.get(telegram_id=telegram_id)
        except CustomUser.DoesNotExist:
            logger.warning(f"Попытка создания задачи с неизвестным telegram_id: {telegram_id}")
            return JsonResponse({'error': 'Пользователь не привязан к Telegram.'}, status=403)

        # Проверка должности
        if not creator.position:
            return JsonResponse({'error': 'У вас нет должности.'}, status=403)

        position_title = creator.position.title.lower()
        if "руководитель" not in position_title and "заместитель" not in position_title:
            logger.warning(f"Пользователь {creator.username} ({position_title}) не имеет прав на создание задач")
            return JsonResponse({'error': 'Только руководители и заместители могут создавать задачи.'}, status=403)

        # Проверка типа задачи
        valid_types = [choice[0] for choice in Task.TYPE_CHOICES]
        if type_code not in valid_types:
            return JsonResponse({'error': f'Неверный тип задачи: {type_code}'}, status=400)

        # Парсинг дат и времени
        try:
            deadline_date = datetime.strptime(deadline_str, '%Y-%m-%d').date()
            deadline_time = datetime.strptime(deadline_time_str, '%H:%M').time() if deadline_time_str else None
        except ValueError:
            return JsonResponse({'error': 'Неверный формат дедлайна или времени.'}, status=400)

        event_date = None
        event_time = None
        if event_date_str:
            try:
                event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
                event_time = datetime.strptime(event_time_str, '%H:%M').time() if event_time_str else None
            except ValueError:
                return JsonResponse({'error': 'Неверный формат даты/времени проведения.'}, status=400)

        # Автоматическая привязка района для районных задач
        district = None
        if type_code == 'district':
            if not creator.district:
                return JsonResponse({'error': 'У вас нет района для создания районной задачи.'}, status=400)
            district = creator.district

        # Создание задачи
        task = Task.objects.create(
            title=title.strip(),
            description=description.strip(),
            type=type_code,
            deadline=deadline_date,
            deadline_time=deadline_time,
            event_date=event_date,
            event_time=event_time,
            district=district,
            created_by_username=creator.username,
            created_by_user_id=creator.id,
            status='open'
        )

        logger.info(f"Задача '{task.title}' успешно создана через бот пользователем {creator.username} "
                    f"(telegram_id: {telegram_id}, район: {district.name if district else 'общий'})")

        return JsonResponse({
            'message': 'Задача успешно создана.',
            'task_id': task.id,
            'title': task.title
        }, status=201)

    except json.JSONDecodeError:
        logger.error("Неверный JSON от бота.")
        return JsonResponse({'error': 'Неверный формат JSON.'}, status=400)
    except Exception as e:
        logger.error(f"Ошибка при создании задачи: {e}", exc_info=True)
        return JsonResponse({'error': 'Внутренняя ошибка сервера.'}, status=500)


# Остальные вьюхи без изменений
class TaskUpdateView(LoginRequiredMixin, UpdateView):
    model = Task
    fields = ['title', 'description', 'type', 'deadline', 'deadline_time', 'event_date', 'event_time', 'district']
    template_name = 'users/task_edit.html'
    success_url = reverse_lazy('tasks')

    def dispatch(self, request, *args, **kwargs):
        task = self.get_object()
        user = request.user
        if not user.position or "руководитель" not in user.position.title.lower():
            messages.error(request, "Только руководитель может редактировать задачи.")
            return redirect('tasks')
        if task.type != 'district':
            messages.error(request, "Вы можете редактировать только районные задачи.")
            return redirect('tasks')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Задача успешно обновлена.")
        return super().form_valid(form)


class TaskDeleteView(LoginRequiredMixin, DeleteView):
    model = Task
    success_url = reverse_lazy('tasks')

    def dispatch(self, request, *args, **kwargs):
        task = self.get_object()
        user = request.user
        if not user.position or "руководитель" not in user.position.title.lower():
            messages.error(request, "Только руководитель может удалять задачи.")
            return redirect('tasks')
        if task.type != 'district':
            messages.error(request, "Вы можете удалять только районные задачи.")
            return redirect('tasks')
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Задача успешно удалена.")
        return super().delete(request, *args, **kwargs)