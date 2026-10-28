from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from ..models import Nota, Pedido
from ..forms.nota import NotaForm, NotaDetalleFormSet
from ..forms.pendientes import PendienteForm
from ..services.busqueda import buscar_texto


def _vincular_pedido_a_nota(nota, pedido):
    """
    Asocia el pedido a la nota y copia sus ítems como NotaDetalle
    (sin pisar los que el usuario ya haya cargado a mano en la nota).
    """
    if pedido.nota_id != nota.pk:
        pedido.nota = nota
        pedido.save(update_fields=["nota"])

    for detalle_pedido in pedido.detalles.select_related("item").all():
        nota.detalles.get_or_create(
            item=detalle_pedido.item,
            defaults={
                "cantidad": detalle_pedido.cantidad,
                "detalle": detalle_pedido.detalle,
            },
        )


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
            pedido = form.cleaned_data.get("pedido")
            if pedido:
                _vincular_pedido_a_nota(nota, pedido)
                messages.success(request, f"Nota actualizada y vinculada al pedido {pedido.numero}.")
            else:
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
            pedido = form.cleaned_data.get("pedido")
            if pedido:
                _vincular_pedido_a_nota(nota, pedido)
                messages.success(request, f"Nota creada y vinculada al pedido {pedido.numero}.")
            else:
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
def pedido_items_por_numero(request):
    """
    Devuelve en JSON los ítems de un pedido (por id o por número), para
    previsualizarlos en la nota sin tener que guardar antes de verlos.
    """
    pedido_id = (request.GET.get("pedido_id") or "").strip()
    numero = (request.GET.get("numero") or "").strip()
    nota_actual_id = (request.GET.get("nota_id") or "").strip()

    pedido = None
    if pedido_id:
        pedido = Pedido.objects.filter(pk=pedido_id).first()
    elif numero:
        pedido = Pedido.objects.filter(numero=numero).first()

    if not pedido:
        return JsonResponse({"encontrado": False})

    items = [
        {
            "item_id": d.item_id,
            "cantidad": d.cantidad,
            "detalle": d.detalle,
        }
        for d in pedido.detalles.select_related("item").all()
    ]
    ya_vinculado_a_otra_nota = (
        pedido.nota_id is not None
        and str(pedido.nota_id) != nota_actual_id
    )
    return JsonResponse({
        "encontrado": True,
        "pedido_id": pedido.pk,
        "pedido_numero": pedido.numero,
        "ya_vinculado_a_otra_nota": ya_vinculado_a_otra_nota,
        "items": items,
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
