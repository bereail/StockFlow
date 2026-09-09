"""Búsqueda de texto insensible a mayúsculas/minúsculas Y a tildes.

El `icontains` de Django ya ignora mayúsculas, pero no tildes: buscar
"clinica" no encontraba "Clínica". `searchable_select.js` ya resuelve esto
del lado del cliente (para los combobox de servicio/patrimonio/item);
`buscar_texto()` es el equivalente del lado del servidor, para los
buscadores de listados que sí pegan contra la base.

Requiere que `sin_acentos` esté registrada como función SQLite — ver
`InventarioConfig.ready()` en apps.py.
"""
import unicodedata

from django.db.models import Func, Q
from django.db.models.functions import Lower


def sin_acentos(texto: str) -> str:
    """café -> cafe. Usada tanto acá (Python) como registrada en SQLite."""
    if not texto:
        return texto
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


class SinAcentos(Func):
    """Wrapper ORM de la función SQLite `sin_acentos`."""
    function = "sin_acentos"


def buscar_texto(queryset, termino, *campos):
    """
    Filtra `queryset` por `termino` en cualquiera de `campos` (nombres de
    campo del modelo, admiten `__` para relaciones), ignorando mayúsculas
    y tildes.
    """
    if not termino:
        return queryset
    termino_norm = sin_acentos(termino).lower()
    anotaciones = {}
    condicion = Q()
    for campo in campos:
        alias = f"_busq_{campo.replace('__', '_')}"
        anotaciones[alias] = SinAcentos(Lower(campo))
        condicion |= Q(**{f"{alias}__icontains": termino_norm})
    return queryset.annotate(**anotaciones).filter(condicion)
