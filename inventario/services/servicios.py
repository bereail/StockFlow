"""
Construcción del historial unificado (timeline) de un Servicio, combinando
eventos de varios modelos que no comparten una tabla ni una noción común de
"evento" (Movimiento, AsignacionImpresora, PatrimonioUnidad, Prestamo,
Reparacion, Pedido, Nota). Cada evento se normaliza a un dict con la misma
forma para poder ordenarlos juntos por fecha en la vista de detalle.
"""
from datetime import date, datetime

from django.utils import timezone as dj_timezone


def _a_datetime(valor):
    """Normaliza date/datetime a datetime aware para poder ordenar junto."""
    if isinstance(valor, datetime):
        return valor
    if isinstance(valor, date):
        return dj_timezone.make_aware(datetime.combine(valor, datetime.min.time()))
    return valor


# Color semántico por tipo de evento (se resuelve una vez acá y no en el
# template): verde = entra/se devuelve, rojo = sale/problema, amarillo =
# en curso, azul = asignación/documento, gris = neutral.
_COLOR_POR_TIPO = {
    "movimiento_ingreso": "ok",
    "movimiento_egreso": "danger",
    "movimiento_ajuste": "warn",
    "impresora_asignada": "primary",
    "impresora_retirada": "muted",
    "patrimonio": "primary",
    "prestamo_inicio": "ok",
    "prestamo_devuelto": "muted",
    "reparacion": "danger",
    "pedido": "warn",
    "pedido_entregado": "ok",
    "nota": "primary",
}


def historial_de_servicio(servicio, limite=40):
    """
    Devuelve una lista de eventos (más reciente primero) para la timeline
    del servicio. Cada evento: {fecha, tipo, titulo, detalle, url, icono}.
    """
    eventos = []

    movimientos = (
        servicio.movimientos.filter(anulado=False)
        .prefetch_related(
            "detalles__item__toner", "detalles__item__articulo",
            "detalles__item__activo_pc", "detalles__item__impresora",
        )
        .order_by("-fecha")[:limite]
    )
    for m in movimientos:
        items = ", ".join(f"{d.item} ×{d.cantidad}" for d in m.detalles.all()) or "—"
        titulo = {"INGRESO": "Ingreso de stock", "EGRESO": "Entrega de stock", "AJUSTE": "Ajuste de stock"}.get(m.tipo, m.tipo)
        eventos.append({
            "fecha": _a_datetime(m.fecha), "tipo": "movimiento_" + m.tipo.lower(),
            "titulo": titulo, "detalle": items,
            "url": "movimiento_edit", "url_pk": m.pk,
        })

    for a in servicio.impresoras_asignadas.select_related("impresora").order_by("-fecha_desde")[:limite]:
        eventos.append({
            "fecha": _a_datetime(a.fecha_desde), "tipo": "impresora_asignada",
            "titulo": "Impresora asignada", "detalle": str(a.impresora),
            "url": "impresora_edit", "url_pk": a.impresora_id,
        })
        if a.fecha_hasta:
            eventos.append({
                "fecha": _a_datetime(a.fecha_hasta), "tipo": "impresora_retirada",
                "titulo": "Impresora retirada", "detalle": str(a.impresora),
                "url": "impresora_edit", "url_pk": a.impresora_id,
            })

    for p in servicio.patrimonios_asignados.select_related("articulo").order_by("-fecha")[:limite]:
        eventos.append({
            "fecha": _a_datetime(p.fecha), "tipo": "patrimonio",
            "titulo": "Alta de patrimonio", "detalle": f"{p.numero_patrimonio} — {p.articulo.nombre if p.articulo else p.detalle_item}",
            "url": "patrimonio_edit", "url_pk": p.pk,
        })

    prestamos_qs = servicio.prestamos.prefetch_related(
        "detalles__item__toner", "detalles__item__articulo",
        "detalles__item__activo_pc", "detalles__item__impresora",
    ).order_by("-fecha_retiro")[:limite]
    for pr in prestamos_qs:
        eventos.append({
            "fecha": _a_datetime(pr.fecha_retiro), "tipo": "prestamo_inicio",
            "titulo": "Préstamo entregado", "detalle": pr.items_label,
            "url": "prestamo_detail", "url_pk": pr.pk,
        })
        if pr.fecha_devolucion_real:
            eventos.append({
                "fecha": _a_datetime(pr.fecha_devolucion_real), "tipo": "prestamo_devuelto",
                "titulo": "Préstamo devuelto", "detalle": pr.items_label,
                "url": "prestamo_detail", "url_pk": pr.pk,
            })

    for r in servicio.reparaciones.select_related("item").order_by("-creado")[:limite]:
        eventos.append({
            "fecha": _a_datetime(r.creado), "tipo": "reparacion",
            "titulo": f"Reparación iniciada ({r.get_estado_display()})", "detalle": str(r.item),
            "url": "reparacion_detail", "url_pk": r.pk,
        })

    for pe in servicio.pedidos.order_by("-creado")[:limite]:
        eventos.append({
            "fecha": _a_datetime(pe.creado), "tipo": "pedido",
            "titulo": f"Pedido {pe.numero}", "detalle": pe.get_estado_display(),
            "url": "pedido_detail", "url_pk": pe.pk,
        })
        if pe.fecha_entregado:
            eventos.append({
                "fecha": _a_datetime(pe.fecha_entregado), "tipo": "pedido_entregado",
                "titulo": f"Pedido {pe.numero} entregado", "detalle": "",
                "url": "pedido_detail", "url_pk": pe.pk,
            })

    for n in servicio.notas.order_by("-fecha")[:limite]:
        eventos.append({
            "fecha": _a_datetime(n.fecha), "tipo": "nota",
            "titulo": f"Nota {n.numero}" if n.numero else "Nota", "detalle": n.get_estado_display(),
            "url": "nota_detail", "url_pk": n.pk,
        })

    eventos.sort(key=lambda e: e["fecha"], reverse=True)
    eventos = eventos[:limite]
    for e in eventos:
        e["color"] = _COLOR_POR_TIPO.get(e["tipo"], "muted")
    return eventos
