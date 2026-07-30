import logging

from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.timezone import is_naive, make_aware
from ..models import Impresora, AsignacionImpresora, Movimiento, MovimientoDetalle
from ..forms.impresoras import ImpresoraForm, EntregaRapidaImpresoraForm
from ..forms.asignaciones import AsignacionImpresoraForm
from ..services.items import item_de_impresora
from ..services.impresoras import asignar_impresora_a_servicio

logger = logging.getLogger(__name__)


@login_required
def impresoras_page(request):
    q = (request.GET.get("q") or "").strip()

    impresoras = (
        Impresora.objects
        .select_related("toner", "articulo")
        .prefetch_related(
            Prefetch(
                "asignaciones",
                queryset=AsignacionImpresora.objects.select_related("servicio").order_by("-fecha_desde"),
            )
        )
        .order_by("-id")
    )

    if q:
        impresoras = impresoras.filter(
            Q(marca__icontains=q) |
            Q(modelo__icontains=q) |
            Q(patrimonio__icontains=q) |
            Q(ip__icontains=q)
        )

    paginator = Paginator(impresoras, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/impresoras/impresoras.html", {
        "impresoras": page_obj, "page_obj": page_obj, "q": q,
    })


@login_required
def asignar_impresora(request, impresora_id):
    impresora = get_object_or_404(Impresora, id=impresora_id)

    if request.method == "POST":
        form = AsignacionImpresoraForm(request.POST)
        if form.is_valid():
            hoy = timezone.localdate()

            AsignacionImpresora.objects.filter(
                impresora=impresora,
                fecha_hasta__isnull=True
            ).update(fecha_hasta=hoy)

            asignacion = form.save(commit=False)
            asignacion.impresora = impresora
            if not asignacion.fecha_desde:
                asignacion.fecha_desde = hoy
            asignacion.save()

            messages.success(request, f"Impresora asignada a {asignacion.servicio} correctamente.")
            return redirect("impresoras_page")
    else:
        form = AsignacionImpresoraForm(initial={"fecha_desde": timezone.localdate()})

    return render(
        request,
        "inventario/impresoras/asignar_impresora.html",
        {"impresora": impresora, "form": form, "title": "Asignar impresora a servicio"},
    )


@login_required
def impresora_create(request):
    if request.method == "POST":
        form = ImpresoraForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Impresora creada.")
            return redirect("impresoras_page")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = ImpresoraForm()

    return render(request, "inventario/impresoras/impresora_form.html", {"form": form, "mode": "create"})


@login_required
def impresora_edit(request, pk):
    impresora = get_object_or_404(Impresora, pk=pk)

    if request.method == "POST":
        form = ImpresoraForm(request.POST, instance=impresora)
        if form.is_valid():
            form.save()
            messages.success(request, "Impresora actualizada.")
            return redirect("impresoras_page")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = ImpresoraForm(instance=impresora)

    return render(request, "inventario/impresoras/impresora_form.html", {"form": form, "mode": "edit", "impresora": impresora})


@login_required
def impresora_toggle(request, pk):
    impresora = get_object_or_404(Impresora, pk=pk)
    impresora.estado = "INACTIVA" if impresora.estado == "ACTIVA" else "ACTIVA"
    impresora.save(update_fields=["estado"])
    return redirect("impresoras_page")


@login_required
def impresora_entrega(request):
    if request.method == "POST":
        form = EntregaRapidaImpresoraForm(request.POST)
        if form.is_valid():
            servicio = form.cleaned_data["servicio"]
            impresora = form.cleaned_data["impresora"]
            observaciones = (form.cleaned_data.get("observaciones") or "").strip()
            fecha = form.cleaned_data.get("fecha") or timezone.now()

            if is_naive(fecha):
                fecha = make_aware(fecha, timezone.get_current_timezone())

            try:
                with transaction.atomic():
                    movimiento = Movimiento.objects.create(
                        tipo="EGRESO",
                        fecha=fecha,
                        servicio=servicio,
                        observaciones=observaciones,
                    )

                    MovimientoDetalle.objects.create(
                        movimiento=movimiento,
                        item=item_de_impresora(impresora),
                        cantidad=1,
                    )

                    # La entrega es, en la práctica, una asignación a ese
                    # servicio: se refleja igual que si se hiciera desde
                    # "Asignar / Mover" o desde la carga de Patrimonio.
                    asignar_impresora_a_servicio(
                        impresora,
                        servicio,
                        fecha=fecha.date(),
                        observaciones=observaciones,
                    )

                messages.success(request, "Movimiento de impresora registrado correctamente.")
                return redirect("impresoras_page")

            except Exception:
                logger.exception("Error al registrar movimiento de entrega de impresora")
                messages.error(request, "No se pudo registrar el movimiento. Intentá de nuevo.")
        else:
            messages.error(request, "Revisá los datos del formulario.")
    else:
        form = EntregaRapidaImpresoraForm()

    return render(request, "inventario/impresoras/impresora_entrega.html", {"form": form})


@login_required
def impresora_historial(request):
    q = (request.GET.get("q") or "").strip()

    detalles = (
        MovimientoDetalle.objects
        .select_related("movimiento", "item", "item__impresora", "movimiento__servicio")
        .filter(movimiento__tipo="EGRESO", item__tipo="IMPRESORA")
        .order_by("-movimiento__fecha")
    )

    if q:
        detalles = detalles.filter(
            Q(item__impresora__marca__icontains=q) |
            Q(item__impresora__modelo__icontains=q) |
            Q(movimiento__servicio__nombre__icontains=q) |
            Q(movimiento__observaciones__icontains=q)
        )

    paginator = Paginator(detalles, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/impresoras/impresoras_historial.html", {
        "detalles": page_obj, "page_obj": page_obj, "q": q,
    })
