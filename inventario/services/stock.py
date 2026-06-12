from django.db.models import Sum
from inventario.models import MovimientoDetalle


def stock_de_item(item_id: int) -> int:
    """
    Stock = ingresos (+) + ajustes (+/-) - egresos (-)
    Los movimientos anulados no se cuentan.
    """
    qs = MovimientoDetalle.objects.filter(
        item_id=item_id,
        movimiento__anulado=False,
    )

    ingresos = qs.filter(movimiento__tipo="INGRESO").aggregate(s=Sum("cantidad"))["s"] or 0
    egresos  = qs.filter(movimiento__tipo="EGRESO").aggregate(s=Sum("cantidad"))["s"] or 0
    ajustes  = qs.filter(movimiento__tipo="AJUSTE").aggregate(s=Sum("cantidad"))["s"] or 0

    return ingresos - egresos + ajustes


def hay_stock_suficiente(item_id: int, cantidad_a_egresar: int) -> bool:
    return stock_de_item(item_id) >= cantidad_a_egresar
