import os
import csv

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, F, Sum, Case, When, IntegerField
from django.db.models.functions import Coalesce
from django.forms import modelformset_factory
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import (
    Toner, Articulo,
    Servicio,
    Documento,
    Item,
    Movimiento, MovimientoDetalle,
)
from .forms import (
    TonerForm,
    ArticuloForm,
    MovimientoForm,
    MovimientoDetalleTonerForm,
    MovimientoDetalleArticuloForm,
    EntregaRapidaTonerForm,   # ✅ IMPORTANTE
)

print("VIEWS VERSION: 2026-01-08 (ITEM + DETALLE) - FIXED")


# =========================
# HELPERS
# =========================

def item_de_toner(toner: Toner) -> Item:
    item, _ = Item.objects.get_or_create(tipo="TONER", toner=toner)
    return item


def item_de_articulo(articulo: Articulo) -> Item:
    item, _ = Item.objects.get_or_create(tipo="ARTICULO", articulo=articulo)
    return item


def stock_de_item(item_id: int) -> int:
    qs = MovimientoDetalle.objects.filter(item_id=item_id)
    ingresos = qs.filter(movimiento__tipo="INGRESO").aggregate(s=Sum("cantidad"))["s"] or 0
    egresos  = qs.filter(movimiento__tipo="EGRESO").aggregate(s=Sum("cantidad"))["s"] or 0
    ajustes  = qs.filter(movimiento__tipo="AJUSTE").aggregate(s=Sum("cantidad"))["s"] or 0
    return ingresos - egresos + ajustes


# =========================
# DASHBOARD
# =========================

def dashboard(request):
    q = (request.GET.get("q") or "").strip()

    # =========================
    # POST: ENTREGA RÁPIDA TONER
    # =========================
    if request.method == "POST" and request.POST.get("action") == "entregar_toner":
        entrega_form = EntregaRapidaTonerForm(request.POST)

        if entrega_form.is_valid():
            servicio = entrega_form.cleaned_data["servicio"]
            toner = entrega_form.cleaned_data["toner"]
            cantidad = entrega_form.cleaned_data["cantidad"]
            documento = entrega_form.cleaned_data.get("documento")
            entregado_a = entrega_form.cleaned_data.get("entregado_a") or ""
            observaciones = entrega_form.cleaned_data.get("observaciones") or ""
            fecha = entrega_form.cleaned_data.get("fecha") or timezone.now()

            try:
                with transaction.atomic():
                    it = item_de_toner(toner)
                    stock_actual = stock_de_item(it.id)

                    if stock_actual < cantidad:
                        raise ValueError(f"Stock insuficiente. Stock actual: {stock_actual}")

                    mov = Movimiento.objects.create(
                        fecha=fecha,
                        tipo="EGRESO",
                        servicio=servicio,
                        documento=documento,
                        observaciones=(
                            f"Entrega rápida. {('Entregado a: ' + entregado_a + '. ') if entregado_a else ''}{observaciones}"
                        ).strip()
                    )

                    MovimientoDetalle.objects.create(
                        movimiento=mov,
                        item=it,
                        cantidad=cantidad
                    )

                messages.success(request, f"Entrega registrada: {toner} x{cantidad} → {servicio}")
                return redirect("dashboard")

            except Exception as e:
                messages.error(request, f"No se pudo registrar la entrega: {e}")
        else:
            messages.error(request, "Revisá los datos de la entrega rápida.")

    else:
        entrega_form = EntregaRapidaTonerForm()

    # =========================
    # GET: DATOS PARA HOME
    # =========================

    items = (
        Item.objects
        .select_related("toner", "articulo")
        .filter(Q(tipo="TONER") | Q(tipo="ARTICULO"))
    )

    if q:
        items = items.filter(
            Q(toner__nombre__icontains=q) |
            Q(toner__marca__icontains=q) |
            Q(toner__modelo_impresora__icontains=q) |
            Q(articulo__nombre__icontains=q) |
            Q(articulo__marca__icontains=q)
        )

    items = items.annotate(
        ing=Coalesce(Sum(Case(
            When(movimientodetalle__movimiento__tipo="INGRESO",
                 then=F("movimientodetalle__cantidad")),
            default=0, output_field=IntegerField(),
        )), 0),
        egr=Coalesce(Sum(Case(
            When(movimientodetalle__movimiento__tipo="EGRESO",
                 then=F("movimientodetalle__cantidad")),
            default=0, output_field=IntegerField(),
        )), 0),
        aj=Coalesce(Sum(Case(
            When(movimientodetalle__movimiento__tipo="AJUSTE",
                 then=F("movimientodetalle__cantidad")),
            default=0, output_field=IntegerField(),
        )), 0),
    ).annotate(
        stock=F("ing") - F("egr") + F("aj")
    ).order_by("tipo", "id")[:80]

    movimientos = (
        Movimiento.objects
        .select_related("servicio", "documento")
        .order_by("-fecha")[:15]
    )

    movimientos_recientes = (
        MovimientoDetalle.objects
        .select_related("movimiento", "item", "item__toner", "item__articulo")
        .order_by("-movimiento__fecha")[:15]
    )

    return render(request, "inventario/dashboard.html", {
        "entrega_form": entrega_form,
        "items": items,
        "movimientos": movimientos,
        "movimientos_recientes": movimientos_recientes,
        "q": q,
    })


# =========================
# TONER CRUD
# =========================

def toner_new(request):
    if request.method == "POST":
        form = TonerForm(request.POST)
        if form.is_valid():
            toner = form.save()
            Item.objects.get_or_create(tipo="TONER", toner=toner)
            messages.success(request, f"Toner guardado: {toner}")
            return redirect("dashboard")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = TonerForm()

    return render(request, "inventario/toner_form.html", {"form": form, "title": "Nuevo toner"})


def toner_list(request):
    q = (request.GET.get("q") or "").strip()
    toners = Toner.objects.all()

    if q:
        toners = toners.filter(
            Q(nombre__icontains=q) |
            Q(marca__icontains=q) |
            Q(modelo_impresora__icontains=q)
        )

    toners = toners.order_by("marca", "nombre")
    return render(request, "inventario/toner_list.html", {"toners": toners, "q": q, "title": "Toners"})


def toner_edit(request, pk):
    toner = get_object_or_404(Toner, pk=pk)

    if request.method == "POST":
        form = TonerForm(request.POST, instance=toner)
        if form.is_valid():
            toner = form.save()
            Item.objects.get_or_create(tipo="TONER", toner=toner)
            messages.success(request, "Toner actualizado.")
            return redirect("toner_list")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = TonerForm(instance=toner)

    return render(request, "inventario/toner_form.html", {"form": form, "title": f"Editar toner #{toner.id}"})


def toner_toggle_active(request, pk):
    toner = get_object_or_404(Toner, pk=pk)

    if request.method == "POST":
        toner.activo = not toner.activo
        toner.save(update_fields=["activo"])
        messages.success(request, "Toner activado." if toner.activo else "Toner desactivado.")
        return redirect("toner_list")

    return render(request, "inventario/toner_toggle_active.html", {"toner": toner})


# =========================
# ARTICULOS CRUD
# =========================

def articulos_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = Articulo.objects.all()

    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(marca__icontains=q))

    qs = qs.order_by("nombre")
    return render(request, "inventario/articulos_list.html", {"articulos": qs, "q": q, "title": "Artículos"})


def articulo_nuevo(request):
    if request.method == "POST":
        form = ArticuloForm(request.POST)
        if form.is_valid():
            art = form.save()
            Item.objects.get_or_create(tipo="ARTICULO", articulo=art)
            messages.success(request, f"Artículo guardado: {art}")
            return redirect("dashboard")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = ArticuloForm()

    return render(request, "inventario/articulo_form.html", {"form": form, "title": "Nuevo artículo"})


def articulo_editar(request, pk):
    art = get_object_or_404(Articulo, pk=pk)

    if request.method == "POST":
        form = ArticuloForm(request.POST, instance=art)
        if form.is_valid():
            art = form.save()
            Item.objects.get_or_create(tipo="ARTICULO", articulo=art)
            messages.success(request, "Artículo actualizado.")
            return redirect("articulos_list")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = ArticuloForm(instance=art)

    return render(request, "inventario/articulo_form.html", {"form": form, "title": f"Editar artículo #{art.id}"})


def articulo_toggle_active(request, pk):
    art = get_object_or_404(Articulo, pk=pk)

    if request.method == "POST":
        art.activo = not art.activo
        art.save(update_fields=["activo"])
        messages.success(request, "Artículo activado." if art.activo else "Artículo desactivado.")
        return redirect("articulos_list")

    return render(request, "inventario/articulo_toggle_active.html", {"articulo": art})


# =========================
# MOVIMIENTOS (CABECERA + 2 FORMSETS)
# =========================

DetalleTonerFormSet = modelformset_factory(
    MovimientoDetalle,
    form=MovimientoDetalleTonerForm,
    extra=0,
    can_delete=True
)

DetalleArticuloFormSet = modelformset_factory(
    MovimientoDetalle,
    form=MovimientoDetalleArticuloForm,
    extra=0,
    can_delete=True
)


def movimiento_new(request):
    if request.method == "POST":
        mov_form = MovimientoForm(request.POST)

        toner_fs = DetalleTonerFormSet(
            request.POST,
            prefix="toner",
            queryset=MovimientoDetalle.objects.none()
        )
        art_fs = DetalleArticuloFormSet(
            request.POST,
            prefix="art",
            queryset=MovimientoDetalle.objects.none()
        )

        if mov_form.is_valid() and toner_fs.is_valid() and art_fs.is_valid():
            toner_items = [
                f for f in toner_fs.cleaned_data
                if f and not f.get("DELETE", False) and f.get("toner") and f.get("cantidad")
            ]
            art_items = [
                f for f in art_fs.cleaned_data
                if f and not f.get("DELETE", False) and f.get("articulo") and f.get("cantidad")
            ]

            if not toner_items and not art_items:
                messages.error(request, "Tenés que cargar al menos un item (toner o artículo).")
            else:
                try:
                    with transaction.atomic():
                        movimiento = mov_form.save()

                        if movimiento.tipo == "EGRESO":
                            for cd in toner_items:
                                it = item_de_toner(cd["toner"])
                                if stock_de_item(it.id) < cd["cantidad"]:
                                    raise ValueError(f"Stock insuficiente para toner: {cd['toner']}")
                            for cd in art_items:
                                it = item_de_articulo(cd["articulo"])
                                if stock_de_item(it.id) < cd["cantidad"]:
                                    raise ValueError(f"Stock insuficiente para artículo: {cd['articulo']}")

                        for cd in toner_items:
                            MovimientoDetalle.objects.create(
                                movimiento=movimiento,
                                item=item_de_toner(cd["toner"]),
                                cantidad=cd["cantidad"],
                            )
                        for cd in art_items:
                            MovimientoDetalle.objects.create(
                                movimiento=movimiento,
                                item=item_de_articulo(cd["articulo"]),
                                cantidad=cd["cantidad"],
                            )

                    messages.success(request, "Movimiento registrado.")
                    return redirect("dashboard")

                except Exception as e:
                    messages.error(request, f"No se pudo registrar el movimiento: {e}")

        else:
            messages.error(request, "Revisá los errores del formulario.")

    else:
        mov_form = MovimientoForm()
        toner_fs = DetalleTonerFormSet(prefix="toner", queryset=MovimientoDetalle.objects.none())
        art_fs = DetalleArticuloFormSet(prefix="art", queryset=MovimientoDetalle.objects.none())

    return render(request, "inventario/movimiento_form.html", {
        "form": mov_form,
        "toner_formset": toner_fs,
        "art_formset": art_fs,
        "title": "Nuevo Movimiento",
    })


def movimientos_list(request):
    tipo = request.GET.get("tipo", "")
    servicio_id = request.GET.get("servicio", "")
    desde = request.GET.get("desde", "")
    hasta = request.GET.get("hasta", "")

    qs = Movimiento.objects.select_related("servicio", "documento").order_by("-fecha")

    if tipo:
        qs = qs.filter(tipo=tipo)
    if servicio_id:
        qs = qs.filter(servicio_id=servicio_id)
    if desde:
        qs = qs.filter(fecha__date__gte=desde)
    if hasta:
        qs = qs.filter(fecha__date__lte=hasta)

    servicios = Servicio.objects.order_by("nombre")

    return render(request, "inventario/movimientos_list.html", {
        "movimientos": qs[:500],
        "servicios": servicios,
        "filtros": {"tipo": tipo, "servicio": servicio_id, "desde": desde, "hasta": hasta},
    })


def movimientos_export_csv(request):
    tipo = request.GET.get("tipo", "")
    servicio_id = request.GET.get("servicio", "")
    desde = request.GET.get("desde", "")
    hasta = request.GET.get("hasta", "")

    qs = Movimiento.objects.select_related("servicio", "documento").order_by("-fecha")

    if tipo:
        qs = qs.filter(tipo=tipo)
    if servicio_id:
        qs = qs.filter(servicio_id=servicio_id)
    if desde:
        qs = qs.filter(fecha__date__gte=desde)
    if hasta:
        qs = qs.filter(fecha__date__lte=hasta)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="movimientos.csv"'
    writer = csv.writer(response)

    writer.writerow([
        "fecha", "tipo", "item_tipo",
        "nombre", "marca", "modelo_impresora",
        "cantidad",
        "servicio",
        "documento_tipo", "documento_numero",
        "observaciones",
    ])

    for m in qs:
        servicio = m.servicio.nombre if m.servicio else ""
        doc_tipo = m.documento.tipo if m.documento else ""
        doc_num = m.documento.numero if m.documento else ""

        detalles = m.detalles.select_related("item", "item__toner", "item__articulo").all()

        for d in detalles:
            if d.item.tipo == "TONER" and d.item.toner:
                t = d.item.toner
                writer.writerow([
                    m.fecha.strftime("%Y-%m-%d %H:%M:%S"),
                    m.tipo,
                    "TONER",
                    t.nombre,
                    t.marca,
                    t.modelo_impresora,
                    d.cantidad,
                    servicio,
                    doc_tipo,
                    doc_num,
                    (m.observaciones or "").replace("\n", " ").strip(),
                ])
            elif d.item.tipo == "ARTICULO" and d.item.articulo:
                a = d.item.articulo
                writer.writerow([
                    m.fecha.strftime("%Y-%m-%d %H:%M:%S"),
                    m.tipo,
                    "ARTICULO",
                    a.nombre,
                    a.marca,
                    "",
                    d.cantidad,
                    servicio,
                    doc_tipo,
                    doc_num,
                    (m.observaciones or "").replace("\n", " ").strip(),
                ])

    return response


def movimiento_anular(request, mov_id):
    mov = get_object_or_404(Movimiento, id=mov_id)

    if hasattr(mov, "anulado") and mov.anulado:
        messages.info(request, "Este movimiento ya fue anulado.")
        return redirect("movimientos_list")

    if request.method == "POST":
        motivo = (request.POST.get("motivo") or "").strip()

        try:
            with transaction.atomic():
                tipo_inverso = "INGRESO" if mov.tipo == "EGRESO" else "EGRESO"

                nuevo = Movimiento.objects.create(
                    fecha=timezone.now(),
                    tipo=tipo_inverso,
                    servicio=mov.servicio if tipo_inverso == "EGRESO" else None,
                    documento=mov.documento,
                    observaciones=f"Anula movimiento #{mov.id}. Motivo: {motivo}",
                )

                for d in mov.detalles.select_related("item").all():
                    MovimientoDetalle.objects.create(
                        movimiento=nuevo,
                        item=d.item,
                        cantidad=d.cantidad,
                    )

                if hasattr(mov, "anulado"):
                    mov.anulado = True
                    mov.anulado_motivo = motivo
                    mov.contramovimiento = nuevo
                    mov.save(update_fields=["anulado", "anulado_motivo", "contramovimiento"])

            messages.success(request, "Movimiento anulado correctamente (se generó el contramovimiento).")

        except Exception as e:
            messages.error(request, f"No se pudo anular: {e}")

        return redirect("movimientos_list")

    return render(request, "inventario/movimiento_anular.html", {"mov": mov})


# =========================
# SERVICIOS
# =========================

def servicios(request):
    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        if nombre:
            Servicio.objects.get_or_create(nombre=nombre)
            messages.success(request, "Servicio guardado.")
            return redirect("servicios")
        messages.error(request, "Nombre requerido.")

    lista = Servicio.objects.order_by("nombre")
    return render(request, "inventario/servicios.html", {"servicios": lista})


# =========================
# BACKUPS
# =========================

def backup_db(request):
    return HttpResponse("Backup endpoint OK")


def _get_backups_dir():
    appdata_dir = os.path.dirname(str(settings.DATABASES["default"]["NAME"]))
    backups_dir = os.path.join(appdata_dir, "backups")
    os.makedirs(backups_dir, exist_ok=True)
    return backups_dir


def abrir_backups(request):
    try:
        backups_dir = _get_backups_dir()
        os.startfile(backups_dir)
        messages.success(request, "Carpeta de backups abierta.")
    except Exception as e:
        messages.error(request, f"No se pudo abrir la carpeta de backups: {e}")

    return redirect("dashboard")
