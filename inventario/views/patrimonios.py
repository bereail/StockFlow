from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from ..models import PedidoDetalle, PatrimonioUnidad
from ..forms.pedidos import PatrimonioUnidadForm
from ..forms.patrimonios import PatrimonioStandaloneForm, DonacionForm


@login_required
def patrimonios_list(request):
    q = (request.GET.get("q") or "").strip()
    tipo = request.GET.get("tipo") or ""

    pats = (
        PatrimonioUnidad.objects
        .select_related(
            "articulo",
            "pedido_detalle__item__articulo",
            "pedido_detalle__item__toner",
            "pedido_detalle__item__activo_pc",
            "pedido_detalle__item__impresora",
            "pedido_detalle__pedido",
            "servicio_asignado",
        )
        .order_by("-id")
    )

    if q:
        pats = pats.filter(
            Q(numero_patrimonio__icontains=q) |
            Q(nombre_pc__icontains=q) |
            Q(ip__icontains=q) |
            Q(usuario_asignado__icontains=q) |
            Q(serial__icontains=q) |
            Q(servicio_asignado__nombre__icontains=q) |
            Q(detalle_item__icontains=q) |
            Q(articulo__nombre__icontains=q) |
            Q(pedido_detalle__item__toner__nombre__icontains=q) |
            Q(pedido_detalle__item__toner__marca__icontains=q) |
            Q(pedido_detalle__item__activo_pc__nombre_pc__icontains=q) |
            Q(pedido_detalle__item__impresora__modelo__icontains=q)
        )

    if tipo == "ARTICULO":
        pats = pats.filter(Q(pedido_detalle__item__tipo="ARTICULO") | Q(articulo__isnull=False))
    elif tipo:
        pats = pats.filter(pedido_detalle__item__tipo=tipo)

    paginator = Paginator(pats, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/patrimonios/list.html", {
        "pats": page_obj, "page_obj": page_obj, "q": q, "tipo": tipo,
    })


@login_required
def patrimonio_detail(request, pk):
    pat = get_object_or_404(
        PatrimonioUnidad.objects.select_related(
            "articulo",
            "servicio_asignado",
            "asignado_por",
            "pedido_detalle__pedido",
            "pedido_detalle__item__toner",
            "pedido_detalle__item__activo_pc",
            "pedido_detalle__item__impresora",
            "pedido_detalle__item__articulo",
        ),
        pk=pk,
    )
    editar_url = "patrimonio_edit" if pat.pedido_detalle_id else "patrimonio_standalone_edit"
    return render(request, "inventario/patrimonios/patrimonio_detail.html", {
        "pat": pat,
        "editar_url": editar_url,
    })


@login_required
def patrimonio_standalone_create(request):
    if request.method == "POST":
        form = PatrimonioStandaloneForm(request.POST, user=request.user)
        if form.is_valid():
            unidad = form.save()
            messages.success(request, f"Patrimonio {unidad.numero_patrimonio} registrado.")
            return redirect("patrimonios_list")
    else:
        form = PatrimonioStandaloneForm(user=request.user)

    return render(request, "inventario/patrimonios/standalone_form.html", {"form": form, "mode": "create"})


@login_required
def patrimonio_standalone_edit(request, pk):
    pat = get_object_or_404(PatrimonioUnidad, pk=pk, pedido_detalle__isnull=True)
    FormClass = DonacionForm if pat.es_donacion else PatrimonioStandaloneForm
    redirect_a = "donaciones_list" if pat.es_donacion else "patrimonios_list"

    if request.method == "POST":
        form = FormClass(request.POST, instance=pat, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Patrimonio actualizado.")
            return redirect(redirect_a)
    else:
        form = FormClass(instance=pat, user=request.user)

    return render(request, "inventario/patrimonios/standalone_form.html", {
        "form": form, "mode": "edit", "patrimonio": pat, "es_donacion": pat.es_donacion,
    })


@login_required
def donaciones_list(request):
    q = (request.GET.get("q") or "").strip()

    donaciones = (
        PatrimonioUnidad.objects
        .filter(es_donacion=True)
        .select_related("articulo", "servicio_asignado")
        .order_by("-id")
    )

    if q:
        donaciones = donaciones.filter(
            Q(numero_patrimonio__icontains=q) |
            Q(donante__icontains=q) |
            Q(donante_contacto__icontains=q) |
            Q(articulo__nombre__icontains=q) |
            Q(servicio_asignado__nombre__icontains=q) |
            Q(detalle_item__icontains=q)
        )

    paginator = Paginator(donaciones, 10)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/patrimonios/donaciones_list.html", {
        "donaciones": page_obj, "page_obj": page_obj, "q": q,
    })


@login_required
def donacion_create(request):
    if request.method == "POST":
        form = DonacionForm(request.POST, user=request.user)
        if form.is_valid():
            unidad = form.save()
            messages.success(request, f"Donación {unidad.numero_patrimonio} registrada.")
            return redirect("donaciones_list")
    else:
        form = DonacionForm(user=request.user)

    return render(request, "inventario/patrimonios/standalone_form.html", {
        "form": form, "mode": "create", "es_donacion": True,
    })


@login_required
def patrimonio_edit(request, pk):
    pat = get_object_or_404(PatrimonioUnidad.objects.select_related("pedido_detalle__pedido"), pk=pk)
    if not pat.pedido_detalle_id:
        return redirect("patrimonio_standalone_edit", pk=pat.pk)
    pedido = pat.pedido_detalle.pedido
    next_url = request.GET.get("next") or request.POST.get("next") or ""
    if request.method == "POST":
        form = PatrimonioUnidadForm(request.POST, instance=pat, pedido_detalle=pat.pedido_detalle, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Patrimonio actualizado.")
            if next_url:
                return redirect(next_url)
            return redirect("pedido_detail", pk=pedido.pk)
    else:
        form = PatrimonioUnidadForm(instance=pat, pedido_detalle=pat.pedido_detalle, user=request.user)
    return render(request, "inventario/pedidos/patrimonio_form.html", {
        "form": form, "detalle": pat.pedido_detalle, "pedido": pedido,
        "cargados": pat.pedido_detalle.patrimonios.count(), "maximo": pat.pedido_detalle.cantidad,
        "modo_edicion": True, "patrimonio": pat, "next": next_url,
    })


@login_required
def patrimonio_create(request, detalle_id):
    detalle = get_object_or_404(
        PedidoDetalle.objects.select_related("pedido", "item"),
        pk=detalle_id
    )
    pedido = detalle.pedido

    if pedido.estado not in ("RECIBIDO", "ENTREGADO", "CERRADO"):
        messages.error(request, "Solo podés cargar patrimonio cuando el pedido esté RECIBIDO (o más).")
        return redirect("pedido_detail", pk=pedido.pk)

    if request.method == "POST":
        form = PatrimonioUnidadForm(request.POST, pedido_detalle=detalle, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Patrimonio cargado.")
            return redirect("pedido_detail", pk=pedido.pk)
    else:
        form = PatrimonioUnidadForm(pedido_detalle=detalle, user=request.user)

    unidades_disponibles = []
    if form.es_articulo_patrimonial:
        unidades_disponibles = (
            PatrimonioUnidad.objects
            .filter(articulo=detalle.item.articulo, pedido_detalle__isnull=True)
            .select_related("servicio_asignado")
            .order_by("numero_patrimonio")
        )

    return render(request, "inventario/pedidos/patrimonio_form.html", {
        "form": form,
        "detalle": detalle,
        "pedido": pedido,
        "cargados": detalle.patrimonios.count(),
        "maximo": detalle.cantidad,
        "unidades_disponibles": unidades_disponibles,
    })


@login_required
@require_POST
def patrimonio_attach(request, detalle_id, pk):
    detalle = get_object_or_404(
        PedidoDetalle.objects.select_related("pedido", "item"),
        pk=detalle_id
    )
    pedido = detalle.pedido
    unidad = get_object_or_404(PatrimonioUnidad, pk=pk, pedido_detalle__isnull=True)

    ya_cargados = detalle.patrimonios.count()
    if ya_cargados >= detalle.cantidad:
        messages.error(request, f"Ya cargaste {ya_cargados}/{detalle.cantidad} patrimonios para este ítem.")
    else:
        unidad.pedido_detalle = detalle
        unidad.save(update_fields=["pedido_detalle"])
        messages.success(request, f"Unidad {unidad.numero_patrimonio} vinculada al pedido.")

    return redirect("pedido_detail", pk=pedido.pk)
