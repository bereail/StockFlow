from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    ############  MOVIMIENTOS #################
    path("movimientos/nuevo/", views.movimiento_new, name="movimiento_new"),
    path("movimientos/<int:mov_id>/anular/", views.movimiento_anular, name="movimiento_anular"),
    path("movimientos/", views.movimientos_list, name="movimientos_list"),
    path("movimientos/export/csv/", views.movimientos_export_csv, name="movimientos_export_csv"),
    
    ############  SERVICIOS #################
    path("servicios/", views.servicios, name="servicios"),

    ############ TONERS #################

    path("toners/", views.toner_list, name="toner_list"),
    path("toners/nuevo/", views.toner_new, name="toner_new"),
    path("toners/<int:pk>/editar/", views.toner_edit, name="toner_edit"),
    path("toners/<int:pk>/estado/", views.toner_toggle_active, name="toner_toggle_active"),

]

# rutas opcionales (no deben romper el arranque)
if hasattr(views, "backup_db"):
    urlpatterns.append(path("backup/", views.backup_db, name="backup_db"))

if hasattr(views, "abrir_backups"):
    urlpatterns.append(path("backups/abrir/", views.abrir_backups, name="abrir_backups"))
