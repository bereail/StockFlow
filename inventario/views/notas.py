from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from ..models import Nota
from ..forms.nota import NotaForm, NotaDetalleFormSet
from ..forms.pendientes import PendienteForm
from ..services.busqueda import buscar_texto


@login_required
@transaction.atomic
def nota_edit(request, pk):
    nota = get_object_or_404(Nota, pk=pk)

    if request.method == "POST":
        form = NotaForm(request.POST, instance=nota)
        formset = NotaDetalleFormSet(request.POST, instance=nota)

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Nota actualizada.")
            return redirect("nota_detail", pk=nota.pk)
    else:
        form = NotaForm(instance=nota)
        formset = NotaDetalleFormSet(instance=nota)

    return render(request, "inventario/notas/form.html", {
        "form": form,
        "formset": formset,
        "modo_edicion": True,
        "nota": nota,
    })


@login_required
@require_POST
@transaction.atomic
def nota_delete(request, pk):
    nota = get_object_or_404(Nota, pk=pk)
    nota.delete()
    messages.success(request, "Nota eliminada.")
    return redirect("notas_list")


_SIGUIENTE_ESTADO_NOTA = {
    "BORRADOR": "ENVIADA",
    "ENVIADA":  "RECIBIDA",
    "RECIBIDA": "ENTREGADA_MESA_ENTRADA",
    "ENTREGADA_MESA_ENTRADA": "FINALIZADA",
}


_PASOS_TIMELINE_NOTA = ["BORRADOR", "ENVIADA", "RECIBIDA", "ENTREGADA_MESA_ENTRADA", "FINALIZADA"]


@login_required
def nota_list(request):
    q      = (request.GET.get("q") or "").strip()
    estado = (request.GET.get("estado") or "").strip()
    notas  = Nota.objects.select_related("servicio_solicitante").order_by("-fecha", "-creado")
    notas = buscar_texto(notas, q, "numero", "servicio_solicitante__nombre", "detalle")
    if estado:
        notas = notas.filter(estado=estado)
    paginator = Paginator(notas, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/notas/lista.html", {
        "notas": page_obj, "page_obj": page_obj,
        "q": q, "estado": estado, "estados": Nota.ESTADOS,
    })


@login_required
@transaction.atomic
def nota_create(request):
    if request.method == "POST":
        form = NotaForm(request.POST)
        formset = NotaDetalleFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            nota = form.save()
            formset.instance = nota
            formset.save()
            messages.success(request, "Nota creada correctamente.")
            return redirect("nota_detail", pk=nota.pk)
    else:
        form = NotaForm()
        formset = NotaDetalleFormSet()

    return render(request, "inventario/notas/form.html", {
        "form": form,
        "formset": formset,
    })


@login_required
def nota_detail(request, pk):
    nota     = get_object_or_404(Nota.objects.select_related("servicio_solicitante"), pk=pk)
    detalles = nota.detalles.select_related("item").all()
    labels   = dict(Nota.ESTADOS)
    paso_actual = _PASOS_TIMELINE_NOTA.index(nota.estado) if nota.estado in _PASOS_TIMELINE_NOTA else -1
    siguiente   = _SIGUIENTE_ESTADO_NOTA.get(nota.estado)
    pendientes = nota.pendientes.select_related("servicio").all()
    pendiente_form = PendienteForm()
    return render(request, "inventario/notas/detalle.html", {
        "nota":            nota,
        "detalles":        detalles,
        "pasos":           [(v, labels.get(v, v)) for v in _PASOS_TIMELINE_NOTA],
        "paso_actual":     paso_actual,
        "siguiente":       siguiente,
        "siguiente_label": labels.get(siguiente, "") if siguiente else "",
        "pendientes":      pendientes,
        "pendiente_form":  pendiente_form,
        "today":           timezone.localdate(),
        "next":            request.GET.get("next") or "",
    })


@login_required
@require_POST
def nota_avanzar(request, pk):
    nota      = get_object_or_404(Nota, pk=pk)
    siguiente = _SIGUIENTE_ESTADO_NOTA.get(nota.estado)
    if siguiente:
        nota.estado = siguiente
        nota.save()
        messages.success(request, f"Nota avanzada a {nota.get_estado_display()}.")
    return redirect("nota_detail", pk=nota.pk)
