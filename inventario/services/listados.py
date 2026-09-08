"""
Ordenamiento seguro para listados: cada vista define qué columnas se pueden
usar para ordenar (una whitelist, nunca el nombre de campo tal cual viene
por GET) y en qué campo real de la base se traduce cada una.
"""


def ordenar(request, queryset, campos: dict, default: str, direccion_default: str = "asc"):
    """
    campos: {"clave_en_la_url": "campo__real_del_modelo", ...}
    default: clave (debe estar en `campos`) usada si no viene `?sort=` o
             viene un valor que no está en la whitelist.
    direccion_default: "asc" o "desc" — con qué dirección arranca `default`
        cuando todavía no se tocó ningún header (ej. listados por fecha
        suelen querer "desc" = más reciente primero).
    Devuelve (queryset_ordenado, clave_actual, direccion_actual).
    """
    clave = request.GET.get("sort") or default
    if clave not in campos:
        clave = default

    direccion = request.GET.get("dir")
    if direccion not in ("asc", "desc"):
        direccion = direccion_default if clave == default else "asc"

    campo_db = campos[clave]
    if direccion == "desc":
        campo_db = f"-{campo_db}"

    return queryset.order_by(campo_db), clave, direccion
