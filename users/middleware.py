import re
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

class LoginExemptMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Компилируем регулярки
        self.exempt_urls = [re.compile(url) for url in getattr(settings, 'LOGIN_EXEMPT_URLS', [])]

    def __call__(self, request):
        # Проверяем путь ДО вызова view
        path = request.path_info.lstrip('/')

        # Если путь в исключениях — пропускаем полностью (GET, POST, всё)
        if any(pattern.match(path) for pattern in self.exempt_urls):
            return self.get_response(request)

        # Если пользователь авторизован — пропускаем
        if request.user.is_authenticated:
            return self.get_response(request)

        # Если не авторизован и путь не исключён — редирект на логин
        # Исключаем сам логин и регистрацию
        if not path.startswith('login') and not path.startswith('register'):
            return redirect(settings.LOGIN_URL)

        return self.get_response(request)
