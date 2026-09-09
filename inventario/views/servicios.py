from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from ..models import (
    AsignacionImpresora, Intercambio, MovimientoDetalle, Servicio,
)
from ..forms.servicios import ServicioForm
from ..services.busqueda import buscar_texto
from ..services.listados import ordenar
from ..services.servicios import historial_de_servicio


@login_required
def servicios_page(request):
    q = (request.GET.get("q") or "").strip()

    servicios = buscar_texto(Servicio.objects.all(), q, "nombre", "descripcion")

    servicios, sort_actual, dir_actual = ordenar(
        request, servicios,
        campos={"nombre": "nombre"},
        default="nombre",
    )

    paginator = Paginator(servicios, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/servicios/servicios.html", {
        "q": q, "servicios": page_obj, "page_obj": page_obj,
        "sort_actual": sort_actual, "dir_actual": dir_actual,
    })


@login_required
def servicio_create(request):
    if request.method == "POST":
        form = ServicioForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Servicio creado.")
            return redirect("servicios_page")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = ServicioForm()

    return render(request, "inventario/servicios/servicio_form.html", {"form": form, "mode": "create"})


@login_required
def servicio_edit(request, pk: int):
    servicio = get_object_or_404(Servicio, pk=pk)

    if request.method == "POST":
        form = ServicioForm(request.POST, instance=servicio)
        if form.is_valid():
            form.save()
            messages.success(request, "Servicio actualizado.")
            return redirect("servicios_page")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = ServicioForm(instance=servicio)

    return render(request, "inventario/servicios/servicio_form.html", {
        "form": form,
        "mode": "edit",
        "servicio": servicio
    })


@login_required
def servicio_detail(request, pk: int):
    servicio = get_object_or_404(Servicio, pk=pk)

    activos_pc = servicio.activos_pc.filter(activo=True).order_by("nombre_pc")

    asignaciones_activas = (
        AsignacionImpresora.objects
        .filter(servicio=servicio, fecha_hasta__isnull=True)
        .select_related("impresora", "impresora__toner")
        .order_by("impresora__marca", "impresora__modelo")
    )

    patrimonios = (
        servicio.patrimonios_asignados
        .select_related("articulo")
        .order_by("-fecha")
    )

    movimientos_recientes = (
        servicio.movimientos.filter(anulado=False)
        .prefetch_related(
            "detalles__item__toner", "detalles__item__articulo",
            "detalles__item__activo_pc", "detalles__item__impresora",
        )
        .order_by("-fecha")[:15]
    )

    prestamos = servicio.prestamos.prefetch_related(
        "detalles__item__toner", "detalles__item__articulo",
        "detalles__item__activo_pc", "detalles__item__impresora",
    ).order_by("-fecha_retiro")
    prestamos_activos = [p for p in prestamos if not p.devuelto]
    prestamos_vencidos = [p for p in prestamos_activos if p.dias_restantes is not None and p.dias_restantes < 0]

    reparaciones = servicio.reparaciones.select_related("item").order_by("-creado")
    reparaciones_activas = reparaciones.exclude(estado__in=["CERRADO", "RETIRADO"])

    pendientes_abiertos = servicio.pendientes.filter(estado__in=["PENDIENTE", "EN_PROGRESO"]).order_by("-id")

    pedidos = servicio.pedidos.order_by("-creado")
    notas = servicio.notas.order_by("-fecha")
    intercambios = (
        Intercambio.objects
        .filter(Q(servicio_afectado=servicio) | Q(servicio_beneficiario=servicio))
        .select_related("servicio_afectado", "servicio_beneficiario")
        .order_by("-fecha_intercambio")
    )

    stats = {
        "pcs": activos_pc.count(),
        "impresoras": asignaciones_activas.count(),
        "patrimonios": patrimonios.count(),
        "movimientos": servicio.movimientos.filter(anulado=False).count(),
        "prestamos_activos": len(prestamos_activos),
        "reparaciones_activas": reparaciones_activas.count(),
        "pendientes_abiertos": pendientes_abiertos.count(),
    }

    historial = historial_de_servicio(servicio, limite=40)

    # ── Estadísticas: entregas de tóner y movimientos totales, últimos 6 meses ──
    hace_6_meses = timezone.now() - timezone.timedelta(days=182)

    entregas_toner_qs = (
        MovimientoDetalle.objects
        .filter(
            movimiento__servicio=servicio, movimiento__anulado=False,
            movimiento__tipo="EGRESO", item__tipo="TONER",
            movimiento__fecha__gte=hace_6_meses,
        )
        .annotate(mes=TruncMonth("movimiento__fecha"))
        .values("mes")
        .annotate(total=Sum("cantidad"))
        .order_by("mes")
    )
    movimientos_por_mes_qs = (
        servicio.movimientos
        .filter(anulado=False, fecha__gte=hace_6_meses)
        .annotate(mes=TruncMonth("fecha"))
        .values("mes")
        .annotate(total=Count("id"))
        .order_by("mes")
    )

    def _serie_con_barras(qs):
        filas = list(qs)
        maximo = max((f["total"] for f in filas), default=0) or 1
        return [
            {"mes": f["mes"], "total": f["total"], "pct": round(f["total"] * 100 / maximo)}
            for f in filas
        ]

    return render(request, "inventario/servicios/servicio_detail.html", {
        "servicio": servicio,
        "stats": stats,
        "activos_pc": activos_pc,
        "asignaciones_activas": asignaciones_activas,
        "patrimonios": patrimonios,
        "movimientos_recientes": movimientos_recientes,
        "prestamos": prestamos,
        "prestamos_vencidos": prestamos_vencidos,
        "reparaciones": reparaciones,
        "reparaciones_activas": reparaciones_activas,
        "pendientes_abiertos": pendientes_abiertos,
        "pedidos": pedidos,
        "notas": notas,
        "intercambios": intercambios,
        "historial": historial,
        "entregas_toner_por_mes": _serie_con_barras(entregas_toner_qs),
        "movimientos_por_mes": _serie_con_barras(movimientos_por_mes_qs),
    })
