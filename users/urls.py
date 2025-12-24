from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView
from django.conf import settings
from django.urls import path, include
from django.conf.urls.static import static
from tasks_app.views import TaskUpdateView


from .views import (
    CustomLoginView, RegisterView, UserListView, UserUpdateView,
    home_dashboard_view, profile_view, tasks_view, reports_view,
    settings_view, get_positions, upload_avatar, UserDeleteView,
    task_create_view, upload_team_photo, telegram_login, task_signup_toggle
)

urlpatterns = [
    # === АУТЕНТИФИКАЦИЯ ===
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('register/', RegisterView.as_view(), name='register'),
    path('upload-avatar/', upload_avatar, name='upload_avatar'),
    path('upload-team-photo/', upload_team_photo, name='upload_team_photo'),

    # === AJAX ===
    path('get-positions/', get_positions, name='get_positions'),

    # === ПРОФИЛЬ ===
    path('profile/', profile_view, name='profile'),
    path('profile/edit/', UserUpdateView.as_view(), name='profile_edit'),

    # === ПОЛЬЗОВАТЕЛИ ===
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/<int:pk>/edit/', UserUpdateView.as_view(), name='user_edit'),
    path('users/<int:pk>/delete/', UserDeleteView.as_view(), name='user_delete'),

    path("telegram-login/", telegram_login, name="telegram_login"),

    # === ЗАДАЧИ ===
    path('tasks/', tasks_view, name='tasks'),
    path('tasks/create/', task_create_view, name='task_create'),
    path('tasks/', include('tasks_app.urls')),
    path('tasks/<int:pk>/edit/', TaskUpdateView.as_view(), name='task_edit'),
    path('tasks/<int:pk>/signup/', task_signup_toggle, name='task_signup'),

    # === ОСТАЛЬНЫЕ РАЗДЕЛЫ ===
    path('reports/', reports_view, name='reports'),
    path('settings/', settings_view, name='settings'),

    # === СБРОС ПАРОЛЯ (должны идти ПОСЛЕ всех остальных, особенно после /create/) ===
    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='users/password_reset.html',
        email_template_name='users/password_reset_email.html',
        subject_template_name='users/password_reset_subject.txt',
    ), name='password_reset'),

    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='users/password_reset_done.html'
    ), name='password_reset_done'),

    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='users/password_reset_confirm.html',
    ), name='password_reset_confirm'),

    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='users/password_reset_complete.html'
    ), name='password_reset_complete'),

    # === API ===
    path('api/', include('tasks_app.urls')),

    # === ГЛАВНАЯ ===
    path('', home_dashboard_view, name='home'),
]

# Медиафайлы в DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
