from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv46_address

from ..models import Articulo, ActivoPC, Impresora, PatrimonioUnidad
from .impresoras import asignar_impresora_a_servicio
from .items import item_de_impresora, item_de_pc


def generar_ficha_desde_articulo(unidad: PatrimonioUnidad, articulo: Articulo) -> None:
    """
    Si el artículo de catálogo está marcado para generar una ficha
    (impresora / activo PC), la creamos recién ahora que ya sabemos el
    N° de patrimonio real, para no perder los datos ricos de esa unidad
    (IP, servicio asignado, etc.) ni obligar a cargarla a mano antes.

    Idempotente: si ya existe una ficha con ese N° de patrimonio (por
    ejemplo porque se está editando un patrimonio que ya la generó),
    no crea una duplicada.
    """
    genera = articulo.genera_ficha
    if not genera:
        return

    ip = unidad.ip or ""
    if ip:
        try:
            validate_ipv46_address(ip)
        except ValidationError:
            ip = ""

    if genera == "IMPRESORA":
        if Impresora.objects.filter(patrimonio=unidad.numero_patrimonio).exists():
            return
        impresora = Impresora.objects.create(
            articulo=articulo,
            marca=articulo.marca or articulo.nombre,
            modelo=unidad.detalle_item or articulo.nombre,
            tipo="",
            patrimonio=unidad.numero_patrimonio,
            conexion="IP" if ip else "USB",
            ip=ip or None,
            observaciones=unidad.observaciones,
        )
        item_de_impresora(impresora)
        if unidad.servicio_asignado:
            asignar_impresora_a_servicio(
                impresora, unidad.servicio_asignado, responsable=unidad.usuario_asignado or "",
            )

    elif genera == "ACTIVO_PC":
        if ActivoPC.objects.filter(patrimonio=unidad.numero_patrimonio).exists():
            return
        pc = ActivoPC.objects.create(
            articulo=articulo,
            nombre_pc=unidad.nombre_pc or unidad.detalle_item or articulo.nombre,
            ip=ip or None,
            patrimonio=unidad.numero_patrimonio,
            serie=unidad.serial,
            observaciones=unidad.observaciones,
            servicio=unidad.servicio_asignado,
        )
        item_de_pc(pc)
