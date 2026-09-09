from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from ..models import Servicio, Pedido, PedidoDetalle
from ..forms.pendientes import PendienteForm
from ..forms.pedidos import PedidoForm, PedidoDetalleFormSet
from ..services.busqueda import buscar_texto


_SIGUIENTE_ESTADO_PEDIDO = {
    "HECHO":    "APROBADO",
    "APROBADO": "RECIBIDO",
    "RECIBIDO": "ENTREGADO",
}


_PASOS_TIMELINE = ["HECHO", "APROBADO", "RECIBIDO", "ENTREGADO"]


@login_required
def pedidos_list(request):
    q = (request.GET.get("q") or "").strip()
    item_q = (request.GET.get("item") or "").strip()
    servicio_id = (request.GET.get("servicio") or "").strip()
    estado = (request.GET.get("estado") or "").strip()

    pedidos = (
        Pedido.objects
        .prefetch_related("servicios")
        .select_related("nota")
        .order_by("-creado")
    )

    pedidos = buscar_texto(pedidos, q, "numero", "nota__numero", "para_que", "observaciones")

    pedidos = buscar_texto(
        pedidos, item_q,
        "detalles__detalle", "detalles__item__toner__nombre", "detalles__item__toner__marca",
        "detalles__item__articulo__nombre", "detalles__item__articulo__descripcion",
        "detalles__item__activo_pc__nombre_pc",
        "detalles__item__impresora__marca", "detalles__item__impresora__modelo",
    )
    if item_q:
        pedidos = pedidos.distinct()

    if servicio_id and servicio_id.lower() != "none":
        try:
            pedidos = pedidos.filter(servicios__id=int(servicio_id)).distinct()
        except ValueError:
            pass

    if estado:
        pedidos = pedidos.filter(estado=estado)

    paginator = Paginator(pedidos, 5)
    page_num  = request.GET.get("page", 1)
    page_obj  = paginator.get_page(page_num)

    return render(request, "inventario/pedidos/list.html", {
        "pedidos":     page_obj,
        "page_obj":    page_obj,
        "q":           q,
        "item_q":      item_q,
        "servicio_id": servicio_id if servicio_id.lower() != "none" else "",
        "estado":      estado,
        "estados":     Pedido.ESTADOS,
        "servicios":   Servicio.objects.order_by("nombre"),
    })


@login_required
def pedido_create(request):
    if request.method == "POST":
        form = PedidoForm(request.POST)
        formset = PedidoDetalleFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            pedido = form.save(commit=False)
            pedido.save()
            form.save_m2m()
            formset.instance = pedido
            formset.save()
            messages.success(request, "Pedido creado.")
            return redirect("pedido_detail", pk=pedido.pk)
    else:
        form = PedidoForm()
        formset = PedidoDetalleFormSet()

    return render(request, "inventario/pedidos/form.html", {
        "form": form,
        "formset": formset,
        "is_edit": False,
    })


@login_required
def pedido_edit(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)

    if request.method == "POST":
        form = PedidoForm(request.POST, instance=pedido)
        formset = PedidoDetalleFormSet(request.POST, instance=pedido)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Pedido actualizado.")
            return redirect("pedido_detail", pk=pedido.pk)
    else:
        form = PedidoForm(instance=pedido)
        formset = PedidoDetalleFormSet(instance=pedido)

    return render(request, "inventario/pedidos/form.html", {
        "form": form,
        "formset": formset,
        "is_edit": True,
        "pedido": pedido,
    })


@login_required
def pedido_detail(request, pk):
    pedido = get_object_or_404(
        Pedido.objects.prefetch_related("servicios").select_related("nota", "nota__servicio_solicitante"),
        pk=pk
    )

    detalles = (
        PedidoDetalle.objects
        .select_related("item")
        .prefetch_related("patrimonios")
        .filter(pedido=pedido)
    )

    siguiente = _SIGUIENTE_ESTADO_PEDIDO.get(pedido.estado)
    labels   = dict(Pedido.ESTADOS)
    paso_actual = _PASOS_TIMELINE.index(pedido.estado) if pedido.estado in _PASOS_TIMELINE else -1
    pasos_display = [(v, labels.get(v, v)) for v in _PASOS_TIMELINE]

    form    = PedidoForm(instance=pedido)
    formset = PedidoDetalleFormSet(instance=pedido)

    pendientes = pedido.pendientes.select_related("servicio").all()
    pendiente_form = PendienteForm()

    nota_detalles = (
        pedido.nota.detalles.select_related(
            "item__articulo", "item__impresora", "item__activo_pc", "item__toner"
        ).all()
        if pedido.nota_id else []
    )

    return render(request, "inventario/pedidos/detail.html", {
        "pedido":          pedido,
        "detalles":        detalles,
        "siguiente":       siguiente,
        "siguiente_label": labels.get(siguiente, "") if siguiente else "",
        "pasos":           pasos_display,
        "paso_actual":     paso_actual,
        "form":            form,
        "formset":         formset,
        "pendientes":      pendientes,
        "pendiente_form":  pendiente_form,
        "today":           timezone.localdate(),
        "nota_detalles":   nota_detalles,
        "next":            request.GET.get("next") or "",
    })


@login_required
@require_POST
def pedido_avanzar(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    siguiente = _SIGUIENTE_ESTADO_PEDIDO.get(pedido.estado)
    if siguiente:
        pedido.estado = siguiente
        hoy = timezone.localdate()
        campos = ["estado", "actualizado"]
        if siguiente == "APROBADO" and not pedido.fecha_aprobado:
            pedido.fecha_aprobado = hoy
            campos.append("fecha_aprobado")
        if siguiente == "RECIBIDO" and not pedido.fecha_recibido:
            pedido.fecha_recibido = hoy
            campos.append("fecha_recibido")
        if siguiente == "ENTREGADO" and not pedido.fecha_entregado:
            pedido.fecha_entregado = hoy
            campos.append("fecha_entregado")
        pedido.save(update_fields=campos)
        messages.success(request, f"Pedido avanzado a {pedido.get_estado_display()}.")
    return redirect("pedido_detail", pk=pedido.pk)


@login_required
@require_POST
def pedido_cancelar(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    if pedido.estado not in ("ENTREGADO", "CANCELADO"):
        pedido.estado = "CANCELADO"
        pedido.save(update_fields=["estado", "actualizado"])
        messages.success(request, "Pedido cancelado.")
    return redirect("pedido_detail", pk=pedido.pk)


@login_required
@require_POST
def pedido_delete(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    pedido.delete()
    messages.success(request, f"Pedido {pedido.numero} eliminado.")
    return redirect("pedidos_list")
