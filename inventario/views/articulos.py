import csv
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from ..models import Articulo, Movimiento, MovimientoDetalle
from ..forms.articulos import ArticuloForm, EntregaRapidaArticuloForm
from ..services.items import item_de_articulo
from ..services.listados import ordenar
from ..services.stock import stock_de_item
from ..services.stock import verificar_stock_suficiente


@login_required
def backup_articulos_csv(request):
    detalles = (MovimientoDetalle.objects
        .select_related("movimiento", "item", "item__articulo", "movimiento__servicio")
        .filter(movimiento__tipo="EGRESO", item__tipo="ARTICULO")
        .order_by("-movimiento__fecha")
    )

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="entregas_articulos.csv"'

    writer = csv.writer(response)
    writer.writerow(["fecha", "servicio", "articulo", "marca", "cantidad", "observaciones"])

    for d in detalles:
        m = d.movimiento
        a = d.item.articulo
        writer.writerow([
            timezone.localtime(m.fecha).strftime("%Y-%m-%d %H:%M"),
            m.servicio.nombre if m.servicio else "",
            a.nombre if a else "",
            a.marca if a else "",
            d.cantidad,
            (m.observaciones or "").replace("\n", " ").strip(),
        ])

    return response


@login_required
def articulos_page(request):
    q = (request.GET.get("q") or "").strip()
    estado = (request.GET.get("estado") or "").strip()

    articulos = Articulo.objects.all()
    if q:
        articulos = articulos.filter(
            Q(nombre__icontains=q) |
            Q(marca__icontains=q) |
            Q(descripcion__icontains=q)
        )
    if estado == "activo":
        articulos = articulos.filter(activo=True)
    elif estado == "inactivo":
        articulos = articulos.filter(activo=False)

    articulos, sort_actual, dir_actual = ordenar(
        request, articulos,
        campos={"marca": "marca", "nombre": "nombre", "estado": "activo"},
        default="nombre",
    )

    paginator = Paginator(articulos, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/articulos/articulos.html", {
        "q": q,
        "estado": estado,
        "articulos": page_obj,
        "page_obj": page_obj,
        "sort_actual": sort_actual,
        "dir_actual": dir_actual,
    })


@login_required
def articulo_detail(request, pk: int):
    articulo = get_object_or_404(Articulo, pk=pk)
    item = item_de_articulo(articulo)
    stock = stock_de_item(item.pk)

    movimientos_recientes = (
        MovimientoDetalle.objects
        .filter(item=item, movimiento__anulado=False)
        .select_related("movimiento", "movimiento__servicio")
        .order_by("-movimiento__fecha")[:10]
    )

    patrimonios = (
        articulo.patrimonios.select_related("servicio_asignado").order_by("-fecha")
        if articulo.es_patrimonial else articulo.patrimonios.none()
    )

    return render(request, "inventario/articulos/articulo_detail.html", {
        "articulo": articulo,
        "stock": stock,
        "movimientos_recientes": movimientos_recientes,
        "patrimonios": patrimonios,
    })


@login_required
def articulo_create(request):
    if request.method == "POST":
        form = ArticuloForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Artículo creado.")
            return redirect("articulos_page")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = ArticuloForm()

    return render(request, "inventario/articulos/articulo_form.html", {"form": form, "mode": "create"})


@login_required
def articulo_edit(request, pk: int):
    articulo = get_object_or_404(Articulo, pk=pk)

    if request.method == "POST":
        form = ArticuloForm(request.POST, instance=articulo)
        if form.is_valid():
            form.save()
            messages.success(request, "Artículo actualizado.")
            return redirect("articulos_page")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = ArticuloForm(instance=articulo)

    return render(request, "inventario/articulos/articulo_form.html", {
        "form": form,
        "mode": "edit",
        "articulo": articulo
    })


@login_required
def articulo_toggle(request, pk: int):
    articulo = get_object_or_404(Articulo, pk=pk)
    articulo.activo = not articulo.activo
    articulo.save(update_fields=["activo"])
    return redirect("articulos_page")


@login_required
def articulo_entrega(request):
    if request.method == "POST":
        form = EntregaRapidaArticuloForm(request.POST)
        if form.is_valid():
            servicio = form.cleaned_data["servicio"]
            articulo = form.cleaned_data["articulo"]
            cantidad = form.cleaned_data["cantidad"]
            unidad = form.cleaned_data.get("unidad_patrimonial")
            observaciones = form.cleaned_data.get("observaciones") or ""
            fecha = form.cleaned_data.get("fecha") or timezone.now()

            try:
                with transaction.atomic():
                    item = item_de_articulo(articulo)
                    verificar_stock_suficiente(item, cantidad)

                    mov = Movimiento.objects.create(
                        tipo="EGRESO",
                        fecha=fecha,
                        servicio=servicio,
                        observaciones=observaciones.strip(),
                    )

                    MovimientoDetalle.objects.create(
                        movimiento=mov,
                        item=item,
                        cantidad=cantidad,
                    )

                    # La entrega de una unidad puntual es, en la práctica, su
                    # asignación actual: queda registrada la misma forma que se
                    # ve después en Patrimonios/Pedidos.
                    if unidad and unidad.servicio_asignado_id != servicio.id:
                        unidad.servicio_asignado = servicio
                        unidad.save(update_fields=["servicio_asignado"])

                return redirect("articulos_page")
            except ValidationError as e:
                messages.error(request, e.message)
    else:
        form = EntregaRapidaArticuloForm()

    return render(request, "inventario/articulos/articulo_entrega.html", {"form": form})


@login_required
def articulos_historial(request):
    q = (request.GET.get("q") or "").strip()
    articulo_id = (request.GET.get("articulo") or "").strip()

    detalles = (MovimientoDetalle.objects
        .select_related("movimiento", "item", "item__articulo", "movimiento__servicio", "movimiento__documento")
        .filter(movimiento__tipo="EGRESO", item__tipo="ARTICULO")
        .order_by("-movimiento__fecha")
    )

    if q:
        detalles = detalles.filter(
            Q(item__articulo__nombre__icontains=q) |
            Q(item__articulo__marca__icontains=q) |
            Q(movimiento__servicio__nombre__icontains=q) |
            Q(movimiento__observaciones__icontains=q)
        )
    if articulo_id:
        detalles = detalles.filter(item__articulo_id=articulo_id)

    paginator = Paginator(detalles, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/articulos/articulos_historial.html", {
        "detalles": page_obj, "page_obj": page_obj, "q": q, "articulo_id": articulo_id,
    })
