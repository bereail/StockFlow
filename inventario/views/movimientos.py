import csv
from django.core.paginator import Paginator
from django.forms import formset_factory
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from ..models import Toner, Servicio, Item, Movimiento, MovimientoDetalle
from ..forms import MovimientoForm, MovimientoDetalleTonerForm, MovimientoDetalleArticuloForm
from ..services.items import item_de_toner, item_de_articulo


TonerFormSet = formset_factory(MovimientoDetalleTonerForm, extra=1, can_delete=True)


ArtFormSet   = formset_factory(MovimientoDetalleArticuloForm, extra=1, can_delete=True)


@login_required
def movimiento_create(request):
    if request.method == "POST":
        form = MovimientoForm(request.POST)
        toner_formset = TonerFormSet(request.POST, prefix="toner")
        art_formset   = ArtFormSet(request.POST, prefix="art")

        if form.is_valid() and toner_formset.is_valid() and art_formset.is_valid():

            def tiene_detalles():
                for f in toner_formset:
                    if f.cleaned_data and not f.cleaned_data.get("DELETE", False):
                        if f.cleaned_data.get("toner") and f.cleaned_data.get("cantidad"):
                            return True
                for f in art_formset:
                    if f.cleaned_data and not f.cleaned_data.get("DELETE", False):
                        if f.cleaned_data.get("articulo") and f.cleaned_data.get("cantidad"):
                            return True
                return False

            if not tiene_detalles():
                messages.error(request, "Agregá al menos un detalle (toner o artículo).")
                return render(request, "inventario/movimientos/movimiento_form.html", {
                    "title": "Nuevo Movimiento",
                    "form": form,
                    "toner_formset": toner_formset,
                    "art_formset": art_formset,
                })

            with transaction.atomic():
                movimiento = form.save()

                for f in toner_formset:
                    if not f.cleaned_data or f.cleaned_data.get("DELETE", False):
                        continue
                    toner = f.cleaned_data.get("toner")
                    cantidad = f.cleaned_data.get("cantidad")
                    if not toner or not cantidad:
                        continue
                    MovimientoDetalle.objects.create(movimiento=movimiento, item=item_de_toner(toner), cantidad=cantidad)

                for f in art_formset:
                    if not f.cleaned_data or f.cleaned_data.get("DELETE", False):
                        continue
                    articulo = f.cleaned_data.get("articulo")
                    cantidad = f.cleaned_data.get("cantidad")
                    if not articulo or not cantidad:
                        continue
                    MovimientoDetalle.objects.create(movimiento=movimiento, item=item_de_articulo(articulo), cantidad=cantidad)

            messages.success(request, "✅ Movimiento guardado.")
            return redirect("movimientos_list")

        messages.error(request, "❌ Revisá el formulario, hay errores.")

    else:
        form = MovimientoForm(initial={"fecha": timezone.now().strftime("%Y-%m-%dT%H:%M")})
        toner_formset = TonerFormSet(prefix="toner")
        art_formset   = ArtFormSet(prefix="art")

    return render(request, "inventario/movimientos/movimiento_form.html", {
        "title": "Nuevo Movimiento",
        "form": form,
        "toner_formset": toner_formset,
        "art_formset": art_formset,
    })


@login_required
def movimientos_list(request):
    servicio_id = request.GET.get("servicio") or ""
    tipo = request.GET.get("tipo") or ""
    q = (request.GET.get("q") or "").strip()

    movimientos = (
        Movimiento.objects
        .select_related("servicio")
        .prefetch_related(
            "detalles__item__toner",
            "detalles__item__articulo",
            "detalles__item__activo_pc",
            "detalles__item__impresora",
        )
        .order_by("-fecha")
    )

    if servicio_id:
        movimientos = movimientos.filter(servicio_id=servicio_id)

    if tipo:
        movimientos = movimientos.filter(tipo=tipo)

    if q:
        movimientos = movimientos.filter(
            Q(observaciones__icontains=q) |
            Q(servicio__nombre__icontains=q) |
            Q(detalles__item__toner__nombre__icontains=q) |
            Q(detalles__item__articulo__nombre__icontains=q)
        ).distinct()

    servicios = Servicio.objects.order_by("nombre")
    toners = Toner.objects.order_by("marca", "nombre")

    filtros = {
        "servicio": servicio_id,
        "tipo": tipo,
        "q": q,
    }

    paginator = Paginator(movimientos, 5)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "inventario/movimientos/movimientos_list.html", {
        "movimientos": page_obj,
        "page_obj": page_obj,
        "servicios": servicios,
        "toners": toners,
        "filtros": filtros,
    })


@login_required
def movimiento_edit(request, pk):
    movimiento = get_object_or_404(Movimiento, pk=pk)
    if request.method == "POST":
        form = MovimientoForm(request.POST, instance=movimiento)
        if form.is_valid():
            form.save()
            messages.success(request, "Movimiento actualizado.")
            return redirect("movimientos_list")
    else:
        form = MovimientoForm(instance=movimiento)
    detalles = movimiento.detalles.select_related(
        "item__toner", "item__articulo", "item__activo_pc", "item__impresora"
    ).all()
    return render(request, "inventario/movimientos/movimiento_edit.html", {
        "form": form, "movimiento": movimiento, "detalles": detalles,
    })


@login_required
@require_POST
def movimiento_anular(request, pk):
    movimiento = get_object_or_404(Movimiento, pk=pk)
    if movimiento.anulado:
        messages.info(request, "Ese movimiento ya estaba anulado.")
    else:
        movimiento.anulado = True
        movimiento.save(update_fields=["anulado"])
        messages.success(request, "Movimiento anulado. Ya no se cuenta en el stock.")
    return redirect("movimientos_list")


@login_required
def movimientos_export_csv(request):
    servicio_id = request.GET.get("servicio")

    qs = (MovimientoDetalle.objects
          .select_related("movimiento", "movimiento__servicio", "item", "item__toner", "item__articulo", "item__activo_pc", "item__impresora")
          .order_by("-movimiento__fecha"))

    if servicio_id:
        qs = qs.filter(movimiento__servicio_id=servicio_id)

    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = f"movimientos_{timezone.now():%Y%m%d_%H%M}.csv"
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(resp)
    writer.writerow(["Fecha", "Tipo", "Servicio", "Item", "Cantidad", "Observaciones"])

    for d in qs:
        mov = d.movimiento
        servicio = mov.servicio.nombre if mov.servicio else "-"
        item_str = str(d.item)

        writer.writerow([
            mov.fecha.strftime("%Y-%m-%d %H:%M"),
            mov.tipo,
            servicio,
            item_str,
            d.cantidad,
            mov.observaciones or "",
        ])

    return resp
