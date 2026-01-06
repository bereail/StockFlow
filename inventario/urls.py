from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),

    # Toners
    path("toners/", views.toner_list, name="toner_list"),
    path("toners/nuevo/", views.toner_new, name="toner_new"),
    path("toners/<int:pk>/editar/", views.toner_edit, name="toner_edit"),
    path("toners/<int:pk>/toggle/", views.toner_toggle_active, name="toner_toggle_active"),

    # Artículos
    path("articulos/", views.articulos_list, name="articulos_list"),
    path("articulos/nuevo/", views.articulo_nuevo, name="articulo_nuevo"),
    path("articulos/<int:pk>/editar/", views.articulo_editar, name="articulo_editar"),
    path("articulos/<int:pk>/toggle/", views.articulo_toggle_active, name="articulo_toggle_active"),

    # Movimientos
    path("movimientos/", views.movimientos_list, name="movimientos_list"),
    path("movimientos/nuevo/", views.movimiento_new, name="movimiento_new"),
    path("movimientos/export/csv/", views.movimientos_export_csv, name="movimientos_export_csv"),
    path("movimientos/<int:mov_id>/anular/", views.movimiento_anular, name="movimiento_anular"),

    # Servicios
    path("servicios/", views.servicios, name="servicios"),

    # Backup / Backups
    path("backup/", views.backup_db, name="backup_db"),
    path("backups/abrir/", views.abrir_backups, name="abrir_backups"),
]
