class AutoLoginMiddleware:
    """
    Login desactivado a pedido (de nuevo): si nadie inició sesión, loguea
    automáticamente con el primer superusuario que exista.

    ADVERTENCIA DE SEGURIDAD: esto anula la autenticación real para
    cualquiera que abra la app. Es una decisión consciente y temporal
    ("por ahora") tomada el 2026-09-07 tras haber sacado este mismo
    bypass por el mismo motivo. Para volver a pedir login: sacar
    "inventario.middleware.AutoLoginMiddleware" de MIDDLEWARE en
    config/settings.py.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            from django.contrib.auth import get_user_model, login
            user = get_user_model().objects.filter(is_superuser=True).order_by("id").first()
            if user:
                login(request, user)
        return self.get_response(request)
