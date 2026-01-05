from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("toners/", views.toner_list, name="toner_list"),
    path("toners/nuevo/", views.toner_new, name="toner_new"),
    path("toners/<int:pk>/editar/", views.toner_edit, name="toner_edit"),
    path("toners/<int:pk>/toggle/", views.toner_toggle_active, name="toner_toggle_active"),

    path("movimientos/", views.movimientos_list, name="movimientos_list"),
    path("movimientos/nuevo/", views.movimiento_new, name="movimiento_new"),
    path("movimientos/export/csv/", views.movimientos_export_csv, name="movimientos_export_csv"),
    path("movimientos/<int:mov_id>/anular/", views.movimiento_anular, name="movimiento_anular"),

    path("servicios/", views.servicios, name="servicios"),

    path("backups/abrir/", views.abrir_backups, name="abrir_backups"),
]
