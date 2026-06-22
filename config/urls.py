from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("inventario.urls")),
]

handler404 = "inventario.views.handler_404"
handler500 = "inventario.views.handler_500"
