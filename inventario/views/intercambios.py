from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from ..models import Intercambio
from ..forms.intercambios import IntercambioForm, IntercambioResolverForm


@login_required
def intercambios_list(request):
    q = (request.GET.get("q") or "").strip()
    estado = request.GET.get("estado") or ""

    intercambios = (
        Intercambio.objects
        .select_related("servicio_afectado", "servicio_beneficiario", "patrimonio_saliente", "patrimonio_entrante")
        .order_by("estado", "-fecha_intercambio")
    )

    if estado:
        intercambios = intercambios.filter(estado=estado)

    if q:
        intercambios = intercambios.filter(
            Q(servicio_afectado__nombre__icontains=q) |
            Q(servicio_beneficiario__nombre__icontains=q) |
            Q(detalle_saliente__icontains=q) |
            Q(detalle_entrante__icontains=q) |
            Q(patrimonio_saliente__numero_patrimonio__icontains=q) |
            Q(patrimonio_entrante__numero_patrimonio__icontains=q) |
            Q(motivo__icontains=q)
        )

    paginator = Paginator(intercambios, 10)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/intercambios/list.html", {
        "intercambios": page_obj, "page_obj": page_obj, "q": q, "estado": estado,
    })


@login_required
def intercambio_create(request):
    if request.method == "POST":
        form = IntercambioForm(request.POST)
        if form.is_valid():
            intercambio = form.save(commit=False)
            intercambio.creado_por = request.user
            intercambio.save()
            if intercambio.patrimonio_saliente_id:
                unidad = intercambio.patrimonio_saliente
                unidad.servicio_asignado = intercambio.servicio_beneficiario
                unidad.save(update_fields=["servicio_asignado"])
            messages.success(request, "Intercambio registrado.")
            return redirect("intercambio_detail", pk=intercambio.pk)
    else:
        form = IntercambioForm()

    return render(request, "inventario/intercambios/form.html", {"form": form})


@login_required
def intercambio_detail(request, pk):
    intercambio = get_object_or_404(
        Intercambio.objects.select_related(
            "servicio_afectado", "servicio_beneficiario",
            "patrimonio_saliente", "patrimonio_entrante", "creado_por", "resuelto_por",
        ),
        pk=pk,
    )
    resolver_form = IntercambioResolverForm() if intercambio.estado == "PENDIENTE" else None
    return render(request, "inventario/intercambios/detail.html", {
        "intercambio": intercambio, "resolver_form": resolver_form,
    })


@login_required
@require_POST
def intercambio_resolver(request, pk):
    intercambio = get_object_or_404(Intercambio, pk=pk)
    if intercambio.estado != "PENDIENTE":
        messages.error(request, "Este intercambio ya no está pendiente.")
        return redirect("intercambio_detail", pk=pk)

    form = IntercambioResolverForm(request.POST, instance=intercambio)
    if form.is_valid():
        intercambio = form.save(commit=False)
        intercambio.estado = "RESUELTO"
        intercambio.fecha_resolucion = timezone.now()
        intercambio.resuelto_por = request.user
        intercambio.save()
        if intercambio.patrimonio_entrante_id:
            unidad = intercambio.patrimonio_entrante
            unidad.servicio_asignado = intercambio.servicio_afectado
            unidad.save(update_fields=["servicio_asignado"])
        messages.success(request, "Intercambio resuelto.")
    else:
        for errores in form.errors.values():
            for error in errores:
                messages.error(request, error)
    return redirect("intercambio_detail", pk=pk)


@login_required
@require_POST
def intercambio_cancelar(request, pk):
    intercambio = get_object_or_404(Intercambio, pk=pk)
    if intercambio.estado == "PENDIENTE":
        intercambio.estado = "CANCELADO"
        intercambio.save(update_fields=["estado"])
        messages.success(request, "Intercambio cancelado.")
    else:
        messages.error(request, "Este intercambio ya no está pendiente.")
    return redirect("intercambio_detail", pk=pk)
