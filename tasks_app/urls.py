from django.urls import path
from .views import create_task_from_telegram
from .views import TaskUpdateView, TaskDeleteView

urlpatterns = [
    path('api/tasks/create/', create_task_from_telegram, name='api_create_task'),
    path('<int:pk>/edit/', TaskUpdateView.as_view(), name='task_edit'),
    path('<int:pk>/delete/', TaskDeleteView.as_view(), name='task_delete'),
]