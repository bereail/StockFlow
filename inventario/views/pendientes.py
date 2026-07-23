from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from ..models import Pendiente, Pedido, Nota
from ..forms.pendientes import PendienteForm


_CICLO_ESTADO = {
    "PENDIENTE":   "EN_PROGRESO",
    "EN_PROGRESO": "COMPLETADO",
    "COMPLETADO":  "PENDIENTE",
    "CANCELADO":   "PENDIENTE",
}


@login_required
def pendientes_page(request):
    if request.method == "POST":
        form = PendienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("pendientes_page")
    else:
        pedido_id = request.GET.get("pedido")
        nota_id = request.GET.get("nota")
        initial = {}
        if pedido_id:
            initial["pedido"] = pedido_id
        if nota_id:
            initial["nota"] = nota_id
        form = PendienteForm(initial=initial or None)

    estado_filtro = (request.GET.get("estado") or "").strip()
    pendientes = Pendiente.objects.select_related("servicio", "pedido", "nota").all()
    if estado_filtro:
        pendientes = pendientes.filter(estado=estado_filtro)

    return render(request, "inventario/pendientes/pendientes.html", {
        "form": form,
        "pendientes": pendientes,
        "estado_filtro": estado_filtro,
        "today": timezone.localdate(),
    })


def _redirect_pendiente(request, pendiente):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url:
        return redirect(next_url)
    if pendiente.pedido_id:
        return redirect("pedido_detail", pk=pendiente.pedido_id)
    if pendiente.nota_id:
        return redirect("nota_detail", pk=pendiente.nota_id)
    return redirect("pendientes_page")


@login_required
@require_POST
def pendiente_toggle(request, pk):
    p = get_object_or_404(Pendiente, pk=pk)
    p.estado = _CICLO_ESTADO.get(p.estado, "PENDIENTE")
    p.save(update_fields=["estado"])
    return _redirect_pendiente(request, p)


@login_required
@require_POST
def pendiente_obs(request, pk):
    p = get_object_or_404(Pendiente, pk=pk)
    p.observacion = (request.POST.get("observacion") or "").strip()
    p.save(update_fields=["observacion"])
    return _redirect_pendiente(request, p)


@login_required
@require_POST
def pendiente_delete(request, pk):
    p = get_object_or_404(Pendiente, pk=pk)
    destino = _redirect_pendiente(request, p)
    p.delete()
    return destino


@login_required
@require_POST
def pendiente_create_for_pedido(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    form = PendienteForm(request.POST)
    if form.is_valid():
        pendiente = form.save(commit=False)
        pendiente.pedido = pedido
        pendiente.save()
        messages.success(request, "Tarea vinculada al pedido.")
    else:
        messages.error(request, "No se pudo crear la tarea: revisá los datos.")
    return redirect("pedido_detail", pk=pedido.pk)


@login_required
@require_POST
def pendiente_create_for_nota(request, pk):
    nota = get_object_or_404(Nota, pk=pk)
    form = PendienteForm(request.POST)
    if form.is_valid():
        pendiente = form.save(commit=False)
        pendiente.nota = nota
        pendiente.save()
        messages.success(request, "Tarea vinculada a la nota.")
    else:
        messages.error(request, "No se pudo crear la tarea: revisá los datos.")
    return redirect("nota_detail", pk=nota.pk)
