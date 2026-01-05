import os
import csv

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, F
from django.forms import modelformset_factory
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404

from .models import (
    Toner, Articulo,
    Movimiento, MovimientoToner, MovimientoArticulo,
    Servicio
)
from .forms import TonerForm, MovimientoForm, MovimientoTonerForm, MovimientoArticuloForm

print("VIEWS VERSION: 2026-01-05 10:40")


# =========================
# DASHBOARD
# =========================
def dashboard(request):
    q = (request.GET.get("q") or "").strip()

    toners = Toner.objects.filter(activo=True)
    if q:
        toners = toners.filter(
            Q(marca__icontains=q) |
            Q(modelo__icontains=q) |
            Q(codigo__icontains=q)
        )
    toners = toners.order_by("marca", "modelo")

    movimientos = Movimiento.objects.select_related("servicio").order_by("-id")[:20]

    stock_bajo = (
        Toner.objects
        .filter(activo=True, minimo__gt=0, stock__lte=F("minimo"))
        .order_by("stock")[:50]
    )

    return render(request, "inventario/dashboard.html", {
        "toners": toners,
        "movimientos": movimientos,
        "stock_bajo": stock_bajo,
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
            messages.success(request, f"Toner guardado: {toner}")
            return redirect("dashboard")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = TonerForm()

    return render(request, "inventario/toner_form.html", {
        "form": form,
        "title": "Nuevo toner"
    })


def toner_list(request):
    q = (request.GET.get("q") or "").strip()
    toners = Toner.objects.all()

    if q:
        toners = toners.filter(
            Q(marca__icontains=q) | Q(modelo__icontains=q) | Q(codigo__icontains=q)
        )

    toners = toners.order_by("marca", "modelo")

    return render(request, "inventario/toner_list.html", {
        "toners": toners,
        "q": q,
        "title": "Toners",
    })


def toner_edit(request, pk):
    toner = get_object_or_404(Toner, pk=pk)

    if request.method == "POST":
        form = TonerForm(request.POST, instance=toner)
        if form.is_valid():
            form.save()
            messages.success(request, "Toner actualizado.")
            return redirect("toner_list")
    else:
        form = TonerForm(instance=toner)

    return render(request, "inventario/toner_form.html", {
        "form": form,
        "title": f"Editar toner #{toner.id}",
    })


def toner_toggle_active(request, pk):
    toner = get_object_or_404(Toner, pk=pk)

    if request.method == "POST":
        toner.activo = not toner.activo
        toner.save()
        messages.success(request, "Toner activado." if toner.activo else "Toner desactivado.")
        return redirect("toner_list")

    return render(request, "inventario/toner_toggle_active.html", {"toner": toner})


# =========================
# MOVIMIENTOS (CABECERA + ITEMS)
# =========================

MovimientoTonerFormSet = modelformset_factory(
    MovimientoToner,
    form=MovimientoTonerForm,
    extra=3,
    can_delete=True
)

MovimientoArticuloFormSet = modelformset_factory(
    MovimientoArticulo,
    form=MovimientoArticuloForm,
    extra=3,
    can_delete=True
)


def movimiento_new(request):
    if request.method == "POST":
        mov_form = MovimientoForm(request.POST)

        toner_fs = MovimientoTonerFormSet(
            request.POST,
            prefix="toner",
            queryset=MovimientoToner.objects.none()
        )
        art_fs = MovimientoArticuloFormSet(
            request.POST,
            prefix="art",
            queryset=MovimientoArticulo.objects.none()
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

                        for cd in toner_items:
                            MovimientoToner.objects.create(
                                movimiento=movimiento,
                                toner=cd["toner"],
                                cantidad=cd["cantidad"],
                            )

                        for cd in art_items:
                            MovimientoArticulo.objects.create(
                                movimiento=movimiento,
                                articulo=cd["articulo"],
                                cantidad=cd["cantidad"],
                            )

                    messages.success(request, "Movimiento registrado y stock actualizado.")
                    return redirect("dashboard")

                except Exception as e:
                    messages.error(request, f"No se pudo registrar el movimiento: {e}")

        else:
            messages.error(request, "Revisá los errores del formulario.")

    else:
        mov_form = MovimientoForm()
        toner_fs = MovimientoTonerFormSet(prefix="toner", queryset=MovimientoToner.objects.none())
        art_fs = MovimientoArticuloFormSet(prefix="art", queryset=MovimientoArticulo.objects.none())

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

    qs = Movimiento.objects.select_related("servicio").order_by("-fecha")

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

    qs = Movimiento.objects.select_related("servicio").order_by("-fecha")

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
        "fecha", "tipo", "item_tipo", "marca", "nombre_modelo", "codigo", "cantidad",
        "servicio", "entregado_a", "observaciones", "anulado", "anulado_motivo",
        "nro_pedido", "nro_nota"
    ])

    for m in qs:
        servicio = m.servicio.nombre if m.servicio else ""
        anulado = "SI" if m.anulado else "NO"

        for it in m.toners.select_related("toner").all():
            t = it.toner
            writer.writerow([
                m.fecha.strftime("%Y-%m-%d %H:%M:%S"),
                m.tipo,
                "TONER",
                t.marca,
                t.modelo,
                t.codigo,
                it.cantidad,
                servicio,
                m.entregado_a or "",
                (m.observaciones or "").replace("\n", " ").strip(),
                anulado,
                m.anulado_motivo or "",
                m.nro_pedido or "",
                m.nro_nota or "",
            ])

        for it in m.articulos.select_related("articulo").all():
            a = it.articulo
            writer.writerow([
                m.fecha.strftime("%Y-%m-%d %H:%M:%S"),
                m.tipo,
                "ARTICULO",
                a.marca,
                a.nombre,
                a.codigo,
                it.cantidad,
                servicio,
                m.entregado_a or "",
                (m.observaciones or "").replace("\n", " ").strip(),
                anulado,
                m.anulado_motivo or "",
                m.nro_pedido or "",
                m.nro_nota or "",
            ])

    return response


def movimiento_anular(request, mov_id):
    mov = get_object_or_404(Movimiento, id=mov_id)

    if mov.anulado:
        messages.info(request, "Este movimiento ya fue anulado.")
        return redirect("movimientos_list")

    if request.method == "POST":
        motivo = (request.POST.get("motivo") or "").strip()

        try:
            with transaction.atomic():
                tipo_inverso = "INGRESO" if mov.tipo == "EGRESO" else "EGRESO"

                nuevo = Movimiento.objects.create(
                    tipo=tipo_inverso,
                    servicio=mov.servicio if tipo_inverso == "EGRESO" else None,
                    entregado_a="ANULACIÓN",
                    observaciones=f"Anula movimiento #{mov.id}. Motivo: {motivo}",
                    nro_pedido=mov.nro_pedido,
                    nro_nota=mov.nro_nota,
                )

                for it in mov.toners.select_related("toner").all():
                    MovimientoToner.objects.create(
                        movimiento=nuevo,
                        toner=it.toner,
                        cantidad=it.cantidad,
                    )

                for it in mov.articulos.select_related("articulo").all():
                    MovimientoArticulo.objects.create(
                        movimiento=nuevo,
                        articulo=it.articulo,
                        cantidad=it.cantidad,
                    )

                mov.anulado = True
                mov.anulado_motivo = motivo
                mov.save(update_fields=["anulado", "anulado_motivo"])

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
