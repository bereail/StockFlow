from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("toners/nuevo/", views.toner_new, name="toner_new"),
    path("movimientos/nuevo/", views.movimiento_new, name="movimiento_new"),
    path("servicios/", views.servicios, name="servicios"),
    path("movimientos/<int:mov_id>/anular/", views.movimiento_anular, name="movimiento_anular"),
    path("movimientos/", views.movimientos_list, name="movimientos_list"),
    path("movimientos/export/csv/", views.movimientos_export_csv, name="movimientos_export_csv"),
]

# rutas opcionales (no deben romper el arranque)
if hasattr(views, "backup_db"):
    urlpatterns.append(path("backup/", views.backup_db, name="backup_db"))

if hasattr(views, "abrir_backups"):
    urlpatterns.append(path("backups/abrir/", views.abrir_backups, name="abrir_backups"))
