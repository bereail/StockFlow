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
    path("toner/reporte/servicios/", views.toner_reporte_servicios, name="toner_reporte_servicios"),
    path("toner/reporte/csv/", views.toner_reporte_csv, name="toner_reporte_csv"),

    # DIAGRAMA BD
    path("diagrama/", views.diagrama_bd, name="diagrama_bd"),

    # REPORTES
    path("reportes/", views.reportes_page, name="reportes"),
    path("reportes/pcs.csv", views.pcs_reporte_csv, name="pcs_reporte_csv"),
    path("reportes/pedidos.csv", views.pedidos_reporte_csv, name="pedidos_reporte_csv"),
    path("reportes/toner.html", views.reporte_toner_html, name="reporte_toner_html"),
    path("reportes/pcs.html", views.reporte_pcs_html, name="reporte_pcs_html"),
    path("reportes/pedidos.html", views.reporte_pedidos_html, name="reporte_pedidos_html"),
    path("reportes/movimientos.html", views.reporte_movimientos_html, name="reporte_movimientos_html"),

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
    path("impresoras/<int:impresora_id>/asignar/", views.asignar_impresora, name="asignar_impresora"),

    # MOVIMIENTOS
    path("movimientos/", views.movimientos_list, name="movimientos_list"),
    path("movimientos/export/csv/", views.movimientos_export_csv, name="movimientos_export_csv"),
    path("movimientos/nuevo/", views.movimiento_create, name="movimiento_create"),
    path("movimientos/<int:pk>/editar/", views.movimiento_edit, name="movimiento_edit"),
    path("movimientos/<int:pk>/anular/", views.movimiento_anular, name="movimiento_anular"),

    # PRESTAMOS
    path("prestamos/", views.prestamos_list, name="prestamos_list"),
    path("mas/prestamos/nuevo/", views.prestamo_create, name="prestamo_create"),
    path("prestamos/<int:pk>/", views.prestamo_detail, name="prestamo_detail"),
    path("prestamos/<int:pk>/editar/", views.prestamo_edit, name="prestamo_edit"),
    path("prestamos/<int:pk>/devolver/", views.prestamo_devolver, name="prestamo_devolver"),

    # INTERCAMBIOS
    path("intercambios/", views.intercambios_list, name="intercambios_list"),
    path("intercambios/nuevo/", views.intercambio_create, name="intercambio_create"),
    path("intercambios/<int:pk>/", views.intercambio_detail, name="intercambio_detail"),
    path("intercambios/<int:pk>/editar/", views.intercambio_edit, name="intercambio_edit"),
    path("intercambios/<int:pk>/resolver/", views.intercambio_resolver, name="intercambio_resolver"),
    path("intercambios/<int:pk>/cancelar/", views.intercambio_cancelar, name="intercambio_cancelar"),

    # PENDIeNTES #
    path("pendientes/", views.pendientes_page, name="pendientes_page"),
    path("pendientes/<int:pk>/toggle/", views.pendiente_toggle, name="pendiente_toggle"),
    path("pendientes/<int:pk>/delete/", views.pendiente_delete, name="pendiente_delete"),
    path("pendientes/<int:pk>/obs/", views.pendiente_obs, name="pendiente_obs"),
    
    # REPARACIONES #
    path("reparaciones/", views.reparaciones_list, name="reparaciones_list"),
    path("reparaciones/nueva/", views.reparacion_create, name="reparacion_create"),
    path("reparaciones/<int:pk>/", views.reparacion_detail, name="reparacion_detail"),
    path("reparaciones/<int:pk>/editar/", views.reparacion_edit, name="reparacion_edit"),
    path("reparaciones/<int:pk>/avanzar/", views.reparacion_avanzar, name="reparacion_avanzar"),

    # PEDIDOS #
    path("pedidos/", views.pedidos_list, name="pedidos_list"),
    path("pedidos/nuevo/", views.pedido_create, name="pedido_create"),
    path("pedidos/<int:pk>/", views.pedido_detail, name="pedido_detail"),
    path("pedidos/<int:pk>/editar/", views.pedido_edit, name="pedido_edit"),
    path("pedidos/<int:pk>/avanzar/", views.pedido_avanzar, name="pedido_avanzar"),
    path("pedidos/<int:pk>/cancelar/", views.pedido_cancelar, name="pedido_cancelar"),
    path("pedidos/<int:pk>/eliminar/", views.pedido_delete, name="pedido_delete"),
    path("pedidos/<int:pk>/pendientes/nuevo/", views.pendiente_create_for_pedido, name="pendiente_create_for_pedido"),
    path("patrimonios/", views.patrimonios_list, name="patrimonios_list"),
    path("patrimonios/nuevo/", views.patrimonio_standalone_create, name="patrimonio_standalone_create"),
    path("patrimonios/donaciones/", views.donaciones_list, name="donaciones_list"),
    path("patrimonios/donaciones/nueva/", views.donacion_create, name="donacion_create"),
    path("patrimonios/<int:pk>/editar-directo/", views.patrimonio_standalone_edit, name="patrimonio_standalone_edit"),
    path("patrimonios/detalle/<int:detalle_id>/nuevo/", views.patrimonio_create, name="patrimonio_create"),
    path("patrimonios/detalle/<int:detalle_id>/vincular/<int:pk>/", views.patrimonio_attach, name="patrimonio_attach"),
    path("patrimonios/<int:pk>/editar/", views.patrimonio_edit, name="patrimonio_edit"),

    # NOTA #
    path("notas/", views.nota_list, name="notas_list"),
    path("notas/nueva/", views.nota_create, name="nota_create"),
    path("notas/<int:pk>/", views.nota_detail, name="nota_detail"),
    path("notas/<int:pk>/editar/", views.nota_edit, name="nota_edit"),
    path("notas/<int:pk>/eliminar/", views.nota_delete, name="nota_delete"),
    path("notas/<int:pk>/avanzar/", views.nota_avanzar, name="nota_avanzar"),

    # BÚSQUEDA GLOBAL
    path("buscar/", views.busqueda_global, name="busqueda_global"),

    # PANEL ADMIN
    path("gestion/", views.admin_panel, name="admin_panel"),
    path("gestion/usuarios/", views.admin_usuarios, name="admin_usuarios"),
    path("gestion/usuarios/nuevo/", views.admin_usuario_create, name="admin_usuario_create"),
    path("gestion/usuarios/<int:pk>/editar/", views.admin_usuario_edit, name="admin_usuario_edit"),
    path("gestion/usuarios/<int:pk>/toggle/", views.admin_usuario_toggle, name="admin_usuario_toggle"),
    path("gestion/usuarios/<int:pk>/eliminar/", views.admin_usuario_delete, name="admin_usuario_delete"),
    path("gestion/roles/", views.admin_roles, name="admin_roles"),
    path("gestion/roles/nuevo/", views.admin_rol_create, name="admin_rol_create"),
    path("gestion/roles/<int:pk>/editar/", views.admin_rol_edit, name="admin_rol_edit"),
    path("gestion/roles/<int:pk>/eliminar/", views.admin_rol_delete, name="admin_rol_delete"),

]
