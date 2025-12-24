from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Подключение стандартной админ-панели
    path('admin/', admin.site.urls),
    path('', include('tasks_app.urls')),

    path('', include('users.urls')),
]
