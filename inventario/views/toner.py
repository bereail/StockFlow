import csv
import io
from datetime import datetime
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from ..models import Toner, Servicio, Movimiento, MovimientoDetalle
from ..forms.toner import TonerForm, EntregaRapidaTonerForm
from ..services.busqueda import buscar_texto
from ..services.items import item_de_toner
from ..services.listados import ordenar
from ..services.stock import stock_de_item, verificar_stock_suficiente


@login_required
def toner_page(request):
    q = (request.GET.get("q") or "").strip()
    estado = (request.GET.get("estado") or "").strip()

    toners = buscar_texto(Toner.objects.all(), q, "nombre", "marca", "modelo_impresora")
    if estado == "activo":
        toners = toners.filter(activo=True)
    elif estado == "inactivo":
        toners = toners.filter(activo=False)

    toners, sort_actual, dir_actual = ordenar(
        request, toners,
        campos={"marca": "marca", "nombre": "nombre", "modelo_impresora": "modelo_impresora", "estado": "activo"},
        default="nombre",
    )

    movimientos_qs = (
        MovimientoDetalle.objects
        .select_related("movimiento", "item", "item__toner", "movimiento__servicio")
        .filter(movimiento__tipo="EGRESO", item__tipo="TONER")
        .order_by("-movimiento__fecha")[:6]
    )

    movimientos = list(movimientos_qs)
    mostrar_ver_todo = len(movimientos) > 5
    movimientos = movimientos[:5]

    paginator = Paginator(toners, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/toner/toner.html", {
        "q": q,
        "estado": estado,
        "toners": page_obj,
        "page_obj": page_obj,
        "sort_actual": sort_actual,
        "dir_actual": dir_actual,
        "movimientos": movimientos,
        "mostrar_ver_todo": mostrar_ver_todo,
    })


@login_required
def toner_list(request):
    q = (request.GET.get("q") or "").strip()
    toners = buscar_texto(Toner.objects.all(), q, "marca", "nombre", "modelo_impresora")
    toners = toners.order_by("marca", "nombre")

    paginator = Paginator(toners, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/toner/toner_list.html", {
        "toners": page_obj,
        "page_obj": page_obj,
        "q": q,
        "title": "Toners",
    })


@login_required
def toner_entrega(request):
    if request.method == "POST":
        form = EntregaRapidaTonerForm(request.POST)
        if form.is_valid():
            servicio = form.cleaned_data["servicio"]
            toner = form.cleaned_data["toner"]
            cantidad = form.cleaned_data["cantidad"]
            entregado_a = form.cleaned_data.get("entregado_a") or ""
            observaciones = form.cleaned_data.get("observaciones") or ""
            fecha = form.cleaned_data.get("fecha") or timezone.now()

            obs = observaciones.strip()
            if entregado_a.strip():
                extra = f"Entregado a: {entregado_a.strip()}"
                obs = f"{extra}\n{obs}".strip() if obs else extra

            try:
                with transaction.atomic():
                    item = item_de_toner(toner)
                    verificar_stock_suficiente(item, cantidad)

                    mov = Movimiento.objects.create(
                        tipo="EGRESO",
                        fecha=fecha,
                        servicio=servicio,
                        observaciones=obs,
                    )

                    MovimientoDetalle.objects.create(
                        movimiento=mov,
                        item=item,
                        cantidad=cantidad,
                    )

                return redirect("toner_page")
            except ValidationError as e:
                messages.error(request, e.message)
    else:
        form = EntregaRapidaTonerForm()

    return render(request, "inventario/toner/toner_entrega.html", {"form": form})


@login_required
def toner_detail(request, pk: int):
    toner = get_object_or_404(Toner, pk=pk)
    item = item_de_toner(toner)
    stock = stock_de_item(item.pk)

    movimientos_recientes = (
        MovimientoDetalle.objects
        .filter(item=item, movimiento__anulado=False)
        .select_related("movimiento", "movimiento__servicio")
        .order_by("-movimiento__fecha")[:10]
    )

    impresoras_compatibles = toner.impresoras.order_by("marca", "modelo")

    return render(request, "inventario/toner/toner_detail.html", {
        "toner": toner,
        "stock": stock,
        "en_stock_critico": toner.stock_minimo > 0 and stock <= toner.stock_minimo,
        "movimientos_recientes": movimientos_recientes,
        "impresoras_compatibles": impresoras_compatibles,
    })


@login_required
def toner_create(request):
    if request.method == "POST":
        form = TonerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Toner creado correctamente.")
            return redirect("toner_page")
        else:
            messages.error(request, "❌ Revisá el formulario, hay errores.")
    else:
        form = TonerForm()

    return render(request, "inventario/toner/toner_form.html", {"form": form, "mode": "create"})


@login_required
def toner_edit(request, pk: int):
    toner = get_object_or_404(Toner, pk=pk)

    if request.method == "POST":
        form = TonerForm(request.POST, instance=toner)
        if form.is_valid():
            form.save()
            return redirect("toner_page")
    else:
        form = TonerForm(instance=toner)

    return render(request, "inventario/toner/toner_form.html", {"form": form, "mode": "edit", "toner": toner})


@login_required
def toner_toggle(request, pk: int):
    toner = get_object_or_404(Toner, pk=pk)
    toner.activo = not toner.activo
    toner.save(update_fields=["activo"])
    return redirect("toner_page")


@login_required
def toner_historial(request):
    q           = (request.GET.get("q") or "").strip()
    servicio_id = (request.GET.get("servicio") or "").strip()
    toner_id    = (request.GET.get("toner") or "").strip()
    fecha_desde = (request.GET.get("fecha_desde") or "").strip()
    fecha_hasta = (request.GET.get("fecha_hasta") or "").strip()

    detalles = (
        MovimientoDetalle.objects
        .select_related("movimiento", "item", "item__toner", "movimiento__servicio", "movimiento__documento")
        .filter(movimiento__tipo="EGRESO", item__tipo="TONER")
        .order_by("-movimiento__fecha")
    )

    detalles = buscar_texto(
        detalles, q,
        "item__toner__nombre", "item__toner__marca", "item__toner__modelo_impresora",
        "movimiento__servicio__nombre", "movimiento__observaciones",
    )
    if servicio_id:
        detalles = detalles.filter(movimiento__servicio_id=servicio_id)
    if toner_id:
        detalles = detalles.filter(item__toner_id=toner_id)
    if fecha_desde:
        try:
            detalles = detalles.filter(
                movimiento__fecha__date__gte=datetime.strptime(fecha_desde, "%Y-%m-%d").date()
            )
        except ValueError:
            pass
    if fecha_hasta:
        try:
            detalles = detalles.filter(
                movimiento__fecha__date__lte=datetime.strptime(fecha_hasta, "%Y-%m-%d").date()
            )
        except ValueError:
            pass

    paginator = Paginator(detalles, 15)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/toner/toner_historial.html", {
        "detalles":    page_obj,
        "page_obj":    page_obj,
        "q":           q,
        "servicio_id": servicio_id,
        "toner_id":    toner_id,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "servicios":   Servicio.objects.order_by("nombre"),
        "toners":      Toner.objects.order_by("nombre"),
    })


@login_required
def backup_entregas_csv(request):
    detalles = (MovimientoDetalle.objects
        .select_related("movimiento", "item", "item__toner", "movimiento__servicio", "movimiento__documento")
        .filter(movimiento__tipo="EGRESO", item__tipo="TONER")
        .order_by("-movimiento__fecha")
    )

    buf = io.StringIO()
    buf.write('﻿')  # BOM UTF-8 para que Excel lo abra bien
    writer = csv.writer(buf)
    writer.writerow(["Fecha", "Servicio", "Toner", "Marca", "Modelo impresora", "Cantidad", "Documento", "Observaciones"])

    for d in detalles:
        m = d.movimiento
        t = d.item.toner
        writer.writerow([
            timezone.localtime(m.fecha).strftime("%Y-%m-%d %H:%M"),
            m.servicio.nombre if m.servicio else "",
            t.nombre if t else "",
            t.marca if t else "",
            t.modelo_impresora if t else "",
            d.cantidad,
            str(m.documento) if m.documento else "",
            (m.observaciones or "").replace("\n", " ").strip(),
        ])

    content = buf.getvalue().encode("utf-8")
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="entregas_toner.csv"'
    return response


@login_required
def toner_reporte_servicios(request):
    """Reporte de tóner agrupado por servicio (o por mes). Filtros: fecha, servicio, toner."""
    servicio_id = (request.GET.get("servicio") or "").strip()
    toner_id    = (request.GET.get("toner") or "").strip()
    fecha_desde = (request.GET.get("fecha_desde") or "").strip()
    fecha_hasta = (request.GET.get("fecha_hasta") or "").strip()
    vista       = (request.GET.get("vista") or "servicio")  # 'servicio' | 'mensual'

    qs = (
        MovimientoDetalle.objects
        .select_related("movimiento__servicio", "item__toner")
        .filter(movimiento__tipo="EGRESO", item__tipo="TONER", movimiento__anulado=False)
    )

    if servicio_id:
        qs = qs.filter(movimiento__servicio_id=servicio_id)
    if toner_id:
        qs = qs.filter(item__toner_id=toner_id)
    if fecha_desde:
        try:
            qs = qs.filter(movimiento__fecha__date__gte=datetime.strptime(fecha_desde, "%Y-%m-%d").date())
        except ValueError:
            pass
    if fecha_hasta:
        try:
            qs = qs.filter(movimiento__fecha__date__lte=datetime.strptime(fecha_hasta, "%Y-%m-%d").date())
        except ValueError:
            pass

    resumen = (
        qs.values(
            "movimiento__servicio__nombre",
            "item__toner__nombre",
            "item__toner__marca",
            "item__toner__modelo_impresora",
        )
        .annotate(total=Sum("cantidad"), entregas=Count("id"))
        .order_by("movimiento__servicio__nombre", "item__toner__nombre")
    )

    # Vista mensual: agrupa por mes → servicio → tóner
    meses = None
    if vista == "mensual":
        filas_mes = (
            qs.annotate(mes=TruncMonth("movimiento__fecha"))
            .values("mes", "movimiento__servicio__nombre",
                    "item__toner__nombre", "item__toner__marca")
            .annotate(total=Sum("cantidad"), entregas=Count("id"))
            .order_by("mes", "movimiento__servicio__nombre", "item__toner__nombre")
        )
        meses_dict = {}
        for f in filas_mes:
            key = f["mes"]
            if key not in meses_dict:
                meses_dict[key] = {"mes": key, "filas": [], "total_mes": 0, "entregas_mes": 0}
            meses_dict[key]["filas"].append(f)
            meses_dict[key]["total_mes"]    += f["total"]
            meses_dict[key]["entregas_mes"] += f["entregas"]
        meses = list(meses_dict.values())

    total_global   = qs.aggregate(total=Sum("cantidad"))["total"] or 0
    total_entregas = qs.count()

    return render(request, "inventario/toner/toner_reporte_servicios.html", {
        "resumen":        resumen,
        "meses":          meses,
        "vista":          vista,
        "total_global":   total_global,
        "total_entregas": total_entregas,
        "servicios":      Servicio.objects.order_by("nombre"),
        "toners":         Toner.objects.filter(activo=True).order_by("nombre"),
        "servicio_id":    servicio_id,
        "toner_id":       toner_id,
        "fecha_desde":    fecha_desde,
        "fecha_hasta":    fecha_hasta,
    })


@login_required
def toner_reporte_csv(request):
    """Descarga CSV del reporte de tóner (con filtros) compatible con Excel."""
    servicio_id = (request.GET.get("servicio") or "").strip()
    toner_id    = (request.GET.get("toner") or "").strip()
    fecha_desde = (request.GET.get("fecha_desde") or "").strip()
    fecha_hasta = (request.GET.get("fecha_hasta") or "").strip()

    qs = (
        MovimientoDetalle.objects
        .select_related("movimiento__servicio", "item__toner")
        .filter(movimiento__tipo="EGRESO", item__tipo="TONER", movimiento__anulado=False)
        .order_by("movimiento__servicio__nombre", "-movimiento__fecha")
    )

    if servicio_id:
        qs = qs.filter(movimiento__servicio_id=servicio_id)
    if toner_id:
        qs = qs.filter(item__toner_id=toner_id)
    if fecha_desde:
        try:
            qs = qs.filter(movimiento__fecha__date__gte=datetime.strptime(fecha_desde, "%Y-%m-%d").date())
        except ValueError:
            pass
    if fecha_hasta:
        try:
            qs = qs.filter(movimiento__fecha__date__lte=datetime.strptime(fecha_hasta, "%Y-%m-%d").date())
        except ValueError:
            pass

    nombre = f"toner_por_servicio_{timezone.now():%Y%m%d}.csv"

    buf = io.StringIO()
    buf.write('﻿')  # BOM UTF-8 para que Excel lo abra bien
    writer = csv.writer(buf)
    writer.writerow(["Fecha", "Servicio", "Toner", "Marca", "Modelo impresora", "Cantidad", "Observaciones"])

    for d in qs:
        m = d.movimiento
        t = d.item.toner
        writer.writerow([
            timezone.localtime(m.fecha).strftime("%Y-%m-%d %H:%M"),
            m.servicio.nombre if m.servicio else "Sin servicio",
            t.nombre if t else "",
            t.marca if t else "",
            t.modelo_impresora if t else "",
            d.cantidad,
            (m.observaciones or "").replace("\n", " ").strip(),
        ])

    content = buf.getvalue().encode("utf-8")
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return response
