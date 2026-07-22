from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from ..models import Reparacion
from ..forms.reparaciones import ReparacionForm


@login_required
def reparaciones_list(request):
    estado = (request.GET.get("estado") or "").strip()
    q      = (request.GET.get("q") or "").strip()
    reparaciones = Reparacion.objects.select_related("item", "proveedor", "servicio").order_by("-creado")
    if estado:
        reparaciones = reparaciones.filter(estado=estado)
    if q:
        reparaciones = reparaciones.filter(
            Q(proveedor__nombre__icontains=q) |
            Q(diagnostico__icontains=q) |
            Q(seguimiento__icontains=q) |
            Q(servicio__nombre__icontains=q)
        )
    paginator = Paginator(reparaciones, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/reparaciones/reparaciones_list.html", {
        "reparaciones": page_obj, "page_obj": page_obj,
        "estado": estado, "q": q, "estados": Reparacion.ESTADOS,
    })


@login_required
def reparacion_detail(request, pk):
    rep      = get_object_or_404(Reparacion.objects.select_related("item", "proveedor", "servicio"), pk=pk)
    labels   = dict(Reparacion.ESTADOS)
    paso_actual = _PASOS_TIMELINE_REP.index(rep.estado) if rep.estado in _PASOS_TIMELINE_REP else -1
    siguiente   = _SIGUIENTE_ESTADO_REP.get(rep.estado)
    return render(request, "inventario/reparaciones/reparacion_detail.html", {
        "rep":             rep,
        "pasos":           [(v, labels.get(v, v)) for v in _PASOS_TIMELINE_REP],
        "paso_actual":     paso_actual,
        "siguiente":       siguiente,
        "siguiente_label": labels.get(siguiente, "") if siguiente else "",
    })


@login_required
@require_POST
def reparacion_avanzar(request, pk):
    rep       = get_object_or_404(Reparacion, pk=pk)
    siguiente = _SIGUIENTE_ESTADO_REP.get(rep.estado)
    if siguiente:
        rep.estado = siguiente
        rep.save(update_fields=["estado", "actualizado"])
        messages.success(request, f"Reparación avanzada a {rep.get_estado_display()}.")
    return redirect("reparacion_detail", pk=rep.pk)


@login_required
def reparacion_create(request):
    if request.method == "POST":
        form = ReparacionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("reparaciones_list")
    else:
        form = ReparacionForm()

    return render(request, "inventario/reparaciones/reparacion_form.html", {
        "form": form,
        "title": "Nueva reparación",
    })


@login_required
def reparacion_edit(request, pk):
    rep = get_object_or_404(Reparacion, pk=pk)

    if request.method == "POST":
        form = ReparacionForm(request.POST, instance=rep)
        if form.is_valid():
            form.save()
            return redirect("reparaciones_list")
    else:
        form = ReparacionForm(instance=rep)

    return render(request, "inventario/reparaciones/reparacion_form.html", {
        "form": form,
        "title": f"Editar reparación #{rep.id}",
        "rep": rep,
    })


_SIGUIENTE_ESTADO_REP = {
    "RECIBIDO":      "ENVIADO",
    "ENVIADO":       "EN_REPARACION",
    "EN_REPARACION": "LISTO",
    "LISTO":         "RETIRADO",
    "RETIRADO":      "CERRADO",
}


_PASOS_TIMELINE_REP = ["RECIBIDO", "ENVIADO", "EN_REPARACION", "LISTO", "RETIRADO", "CERRADO"]
