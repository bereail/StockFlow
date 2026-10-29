from django.core.exceptions import ValidationError
from django.db.models import F, Sum
from inventario.models import Item, MovimientoDetalle


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


def stock_armable_de_combo(item) -> int:
    """
    Cuántas unidades de un item combo se pueden armar hoy con el stock
    disponible de sus componentes: el mínimo, entre todos los componentes,
    de "stock del componente // cantidad que necesita cada combo". Un combo
    sin componentes cargados no se puede armar. Nunca negativo: si algún
    componente arrastra stock negativo (dato histórico, ver detalle del
    artículo), "se pueden armar 0" es más claro que un número negativo.
    """
    componentes = list(item.componentes.all())
    if not componentes:
        return 0
    armable = min(stock_de_item(c.item_hijo_id) // c.cantidad for c in componentes)
    return max(armable, 0)


def lock_item_para_egreso(item) -> None:
    """
    Serializa los egresos concurrentes del mismo item (o, si es un combo, de
    cada uno de sus componentes). Debe llamarse dentro de la misma
    transacción atómica que `verificar_stock_suficiente()`, y ANTES, para
    evitar que dos requests simultáneos lean "hay stock suficiente" cada uno
    por separado antes de que cualquiera llegue a escribir (ver STK-02 de la
    auditoría de 2026-10-23).

    Un UPDATE (aunque no cambie nada) es una escritura real: en SQLite fuerza
    la adquisición del lock exclusivo de inmediato en vez de recién al final
    de la transacción, así que el segundo request concurrente queda bloqueado
    acá hasta que el primero haga commit, y entonces lee el stock ya
    descontado. En Postgres, el UPDATE ya toma el row lock por sí solo.
    """
    if item.es_combo:
        hijo_ids = list(item.componentes.values_list("item_hijo_id", flat=True))
        if hijo_ids:
            Item.objects.filter(pk__in=hijo_ids).update(tipo=F("tipo"))
        return
    Item.objects.filter(pk=item.pk).update(tipo=F("tipo"))


def verificar_stock_suficiente(item, cantidad_a_egresar: int) -> None:
    """
    Levanta ValidationError si un egreso dejaría el stock del item (o, si es
    un combo, el de alguno de sus componentes) en negativo. Debe llamarse
    dentro de la misma transacción que crea el MovimientoDetalle de egreso,
    para que la validación vea el stock más actualizado posible.
    """
    if item.es_combo:
        _verificar_stock_combo_suficiente(item, cantidad_a_egresar)
        return
    disponible = stock_de_item(item.pk)
    if disponible < cantidad_a_egresar:
        raise ValidationError(
            f"Stock insuficiente para «{item}»: disponible {disponible}, se pidió {cantidad_a_egresar}."
        )


def _verificar_stock_combo_suficiente(item, cantidad_a_egresar: int) -> None:
    componentes = list(item.componentes.select_related(
        "item_hijo__toner", "item_hijo__articulo", "item_hijo__activo_pc", "item_hijo__impresora",
    ))
    if not componentes:
        raise ValidationError(f"«{item}» es un combo sin componentes cargados: no se puede entregar.")

    faltantes = []
    for comp in componentes:
        necesario = comp.cantidad * cantidad_a_egresar
        disponible = stock_de_item(comp.item_hijo_id)
        if disponible < necesario:
            faltantes.append(f"«{comp.item_hijo}»: disponible {disponible}, se necesitan {necesario}")
    if faltantes:
        raise ValidationError(
            f"Stock insuficiente en los componentes de «{item}»: " + "; ".join(faltantes)
        )


def crear_detalle_egreso(movimiento, item, cantidad) -> MovimientoDetalle:
    """
    Crea el MovimientoDetalle de un egreso. Si el item es un combo, además
    descuenta cada componente agregando un MovimientoDetalle de egreso por
    cada uno (cantidad del componente × cantidad de combos), en el mismo
    Movimiento — así queda todo en la misma cabecera/comprobante, y anular el
    movimiento anula automáticamente tanto el combo como sus componentes.
    Debe llamarse después de `verificar_stock_suficiente()` para ese mismo
    item, dentro de la misma transacción.
    """
    detalle = MovimientoDetalle.objects.create(movimiento=movimiento, item=item, cantidad=cantidad)
    if item.es_combo:
        for comp in item.componentes.all():
            MovimientoDetalle.objects.create(
                movimiento=movimiento, item=comp.item_hijo, cantidad=comp.cantidad * cantidad,
            )
    return detalle
