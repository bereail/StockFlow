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
