import csv
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

    articulos = Articulo.objects.all().order_by("marca", "nombre")
    if q:
        articulos = articulos.filter(
            Q(nombre__icontains=q) |
            Q(marca__icontains=q) |
            Q(descripcion__icontains=q)
        )

    paginator = Paginator(articulos, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/articulos/articulos.html", {
        "q": q,
        "articulos": page_obj,
        "page_obj": page_obj,
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

            with transaction.atomic():
                mov = Movimiento.objects.create(
                    tipo="EGRESO",
                    fecha=fecha,
                    servicio=servicio,
                    observaciones=observaciones.strip(),
                )

                MovimientoDetalle.objects.create(
                    movimiento=mov,
                    item=item_de_articulo(articulo),
                    cantidad=cantidad,
                )

                # La entrega de una unidad puntual es, en la práctica, su
                # asignación actual: queda registrada la misma forma que se
                # ve después en Patrimonios/Pedidos.
                if unidad and unidad.servicio_asignado_id != servicio.id:
                    unidad.servicio_asignado = servicio
                    unidad.save(update_fields=["servicio_asignado"])

            return redirect("articulos_page")
    else:
        form = EntregaRapidaArticuloForm()

    return render(request, "inventario/articulos/articulo_entrega.html", {"form": form})


@login_required
def articulos_historial(request):
    q = (request.GET.get("q") or "").strip()

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

    paginator = Paginator(detalles, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/articulos/articulos_historial.html", {
        "detalles": page_obj, "page_obj": page_obj, "q": q,
    })
