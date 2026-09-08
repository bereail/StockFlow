from django.core.exceptions import ValidationError
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


def toners_con_stock_critico():
    """
    Tóners activos con stock_minimo configurado (> 0) cuyo stock actual
    está en ese mínimo o por debajo. Pensado para el dashboard: la lista de
    tóners con umbral suele ser chica, así que se resuelve con una consulta
    por tóner en vez de optimizar prematuramente con agregaciones masivas.
    """
    from inventario.models import Toner
    from inventario.services.items import item_de_toner

    criticos = []
    for toner in Toner.objects.filter(activo=True, stock_minimo__gt=0).order_by("nombre"):
        item = item_de_toner(toner)
        stock = stock_de_item(item.pk)
        if stock <= toner.stock_minimo:
            criticos.append({"toner": toner, "stock": stock})
    return criticos


def verificar_stock_suficiente(item, cantidad_a_egresar: int) -> None:
    """
    Levanta ValidationError si un egreso dejaría el stock del item en negativo.
    Debe llamarse dentro de la misma transacción que crea el MovimientoDetalle
    de egreso, para que la validación vea el stock más actualizado posible.
    """
    disponible = stock_de_item(item.pk)
    if disponible < cantidad_a_egresar:
        raise ValidationError(
            f"Stock insuficiente para «{item}»: disponible {disponible}, se pidió {cantidad_a_egresar}."
        )
