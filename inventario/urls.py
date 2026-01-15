from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    # TONER
    path("toner/", views.toner_page, name="toner_page"),
    path("toner/lista/", views.toner_list, name="toner_list"),
    path("toner/entrega/", views.toner_entrega, name="toner_entrega"),
    path("toner/nuevo/", views.toner_create, name="toner_create"),
    path("toner/<int:pk>/editar/", views.toner_edit, name="toner_edit"),
    path("toner/<int:pk>/toggle/", views.toner_toggle, name="toner_toggle"),
    path("toner/historial/", views.toner_historial, name="toner_historial"),
    path("toner/backup/entregas.csv", views.backup_entregas_csv, name="backup_entregas_csv"),

    # ARTICULOS
    path("articulos/", views.articulos_page, name="articulos_page"),
    path("articulos/nuevo/", views.articulo_create, name="articulo_create"),
    path("articulos/<int:pk>/editar/", views.articulo_edit, name="articulo_edit"),
    path("articulos/<int:pk>/toggle/", views.articulo_toggle, name="articulo_toggle"),
    path("articulos/entrega/", views.articulo_entrega, name="articulo_entrega"),
    path("articulos/historial/", views.articulos_historial, name="articulos_historial"),
    path("articulos/backup/entregas.csv", views.backup_articulos_csv, name="backup_articulos_csv"),

    # SERVICIOS
    path("servicios/", views.servicios_page, name="servicios_page"),
    path("servicios/nuevo/", views.servicio_create, name="servicio_create"),
    path("servicios/<int:pk>/editar/", views.servicio_edit, name="servicio_edit"),

    # PCS
    path("pcs/", views.pcs_page, name="pcs_page"),
    path("pcs/nuevo/", views.pcs_create, name="pcs_create"),
    path("pcs/<int:pk>/editar/", views.pcs_edit, name="pcs_edit"),

    # IMPRESORAS
    path("impresoras/", views.impresoras_page, name="impresoras_page"),
    path("impresoras/nuevo/", views.impresora_create, name="impresora_create"),
    path("impresoras/<int:pk>/editar/", views.impresora_edit, name="impresora_edit"),
    path("impresoras/<int:pk>/toggle/", views.impresora_toggle, name="impresora_toggle"),
    path("impresoras/entrega/", views.impresora_entrega, name="impresora_entrega"),
    path("impresoras/historial/", views.impresora_historial, name="impresora_historial"),

    # MOVIMIENTOS
    path("movimientos/", views.movimientos_list, name="movimientos_list"),

    # PROYECTOR #
    path("mas/proyector/", views.proyector_prestamos_page, name="proyector_prestamos_page"),
    path("mas/proyector/nuevo/", views.proyector_prestamo_create, name="proyector_prestamo_create"),
    path("mas/proyector/<int:pk>/devolver/", views.proyector_prestamo_devolver, name="proyector_prestamo_devolver"),

    # PENDIeNTES #
     path("pendientes/", views.pendientes_page, name="pendientes_page"),
    path("pendientes/<int:pk>/toggle/", views.pendiente_toggle, name="pendiente_toggle"),
    path("pendientes/<int:pk>/delete/", views.pendiente_delete, name="pendiente_delete"),
]
