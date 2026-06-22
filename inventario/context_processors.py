from django.conf import settings

MAS_URLS = {
    "prestamos_list", "prestamos_page", "prestamo_create", "prestamo_detail",
    "prestamo_edit", "prestamo_devolver",
    "pendientes_page",
    "reparaciones_list", "reparacion_create", "reparacion_edit",
    "pedidos_list", "pedido_create", "pedido_detail", "pedido_edit",
    "notas_list", "nota_create", "nota_detail", "nota_edit", "nota_delete",
    "patrimonio_create", "busqueda_global",
}

def global_settings(request):
    url_name = getattr(request.resolver_match, "url_name", "") or ""
    return {
        "settings": settings,
        "nav_mas_activo": url_name in MAS_URLS,
    }
