from django.utils import timezone
from ..models import AsignacionImpresora


def asignar_impresora_a_servicio(impresora, servicio, *, fecha=None, responsable="", ubicacion="", observaciones=""):
    """
    Única fuente de verdad para "a qué servicio pertenece esta impresora":
    cierra la asignación activa (si cambia) y abre una nueva. La usan
    Impresoras > Asignar/Mover, Entrega rápida y la carga de Patrimonio en
    un pedido, para que la impresora siempre muestre el mismo servicio sin
    importar por dónde se la haya asignado.
    """
    actual = impresora.servicio_actual
    if servicio == actual:
        return None

    fecha = fecha or timezone.localdate()
    AsignacionImpresora.objects.filter(
        impresora=impresora, fecha_hasta__isnull=True
    ).update(fecha_hasta=fecha)

    if not servicio:
        return None

    return AsignacionImpresora.objects.create(
        impresora=impresora,
        servicio=servicio,
        fecha_desde=fecha,
        responsable=responsable,
        ubicacion=ubicacion,
        observaciones=observaciones,
    )
