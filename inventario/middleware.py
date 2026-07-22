class LocalhostCSRFMiddleware:
    """
    Desactiva la verificación CSRF para peticiones desde 127.0.0.1.
    Seguro para apps de escritorio que solo corren en localhost.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.META.get("REMOTE_ADDR") in ("127.0.0.1", "::1"):
            request._dont_enforce_csrf_checks = True
        return self.get_response(request)


class AutoLoginMiddleware:
    """
    Login deshabilitado momentáneamente (a pedido): si nadie inició sesión,
    loguea automáticamente con el primer superusuario que exista.

    Para volver a pedir login: sacar "inventario.middleware.AutoLoginMiddleware"
    de MIDDLEWARE en config/settings.py.
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

