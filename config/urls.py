from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.contrib.auth.views import LogoutView
from inventario import views as inv_views

urlpatterns = [
    path("favicon.ico", lambda req: HttpResponse(status=204)),
    path("admin/", admin.site.urls),
    path("accounts/login/", inv_views.custom_login, name="login"),
    path("accounts/logout/", LogoutView.as_view(next_page="login"), name="logout"),
    path("", include("inventario.urls")),
]

handler404 = "inventario.views.handler_404"
handler500 = "inventario.views.handler_500"
