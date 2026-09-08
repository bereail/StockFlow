from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag(takes_context=True)
def sort_th(context, campo, etiqueta, sort_actual="", dir_actual="asc"):
    """
    Encabezado de columna ordenable: <th>{% sort_th "nombre" "Nombre" sort dir %}</th>
    Arma el link preservando el resto de los filtros de la URL (q, servicio,
    etc.) y reseteando la paginación al cambiar de orden.
    """
    request = context["request"]
    params = request.GET.copy()
    nueva_direccion = "desc" if (sort_actual == campo and dir_actual == "asc") else "asc"
    params["sort"] = campo
    params["dir"] = nueva_direccion
    params.pop("page", None)

    flecha = ""
    if sort_actual == campo:
        flecha = " ↑" if dir_actual == "asc" else " ↓"

    return format_html(
        '<a class="sort-th{}" href="?{}">{}{}</a>',
        " is-active" if sort_actual == campo else "",
        params.urlencode(),
        etiqueta,
        flecha,
    )
