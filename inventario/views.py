import csv
import io
from datetime import datetime
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.views import LogoutView
from django.core.paginator import Paginator
from django.forms import formset_factory, modelformset_factory
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Prefetch, Sum, Count
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.timezone import is_naive, make_aware
from django.views.decorators.http import require_POST
from .models import (
    Toner, Articulo, Servicio, ActivoPC, Impresora,
    AsignacionImpresora,
    Item, Movimiento, MovimientoDetalle,
    Pendiente, Reparacion,
    Prestamo,
    Pedido, PedidoDetalle, PatrimonioUnidad,
    Nota, NotaDetalle
)
from .forms import (
    MovimientoForm,
    MovimientoDetalleTonerForm,
    MovimientoDetalleArticuloForm,
)
from .forms.toner import TonerForm, EntregaRapidaTonerForm
from .forms.articulos import ArticuloForm, EntregaRapidaArticuloForm
from .forms.servicios import ServicioForm
from .forms.pcs import ActivoPCForm
from .forms.impresoras import ImpresoraForm, EntregaRapidaImpresoraForm
from .forms.prestamos import PrestamoForm, PrestamoDetalleFormSet
from .forms.pendientes import PendienteForm
from .forms.reparaciones import ReparacionForm
from .forms.pedidos import PedidoForm, PedidoDetalleFormSet, PatrimonioUnidadForm
from .forms.asignaciones import AsignacionImpresoraForm
from .forms.nota import NotaForm, NotaDetalleFormSet
from .services.items import item_de_toner, item_de_articulo, item_de_impresora


def custom_login(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    error = False
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        remember  = request.POST.get("remember_me") == "on"
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            if remember:
                request.session.set_expiry(60 * 60 * 24 * 14)  # 14 días
            else:
                request.session.set_expiry(0)  # se cierra con el navegador
            next_url = request.POST.get("next") or request.GET.get("next") or "dashboard"
            return redirect(next_url)
        error = True
    return render(request, "registration/login.html", {"error": error, "next": request.GET.get("next", "")})


@login_required
def dashboard(request):
    stats = {
        "toners":      Toner.objects.filter(activo=True).count(),
        "impresoras":  Impresora.objects.filter(activo=True).count(),
        "articulos":   Articulo.objects.filter(activo=True).count(),
        "servicios":   Servicio.objects.count(),
        "pcs":         ActivoPC.objects.filter(activo=True).count(),
        "prestamos_activos": Prestamo.objects.filter(fecha_devolucion_real__isnull=True).count(),
        "pendientes_abiertos": Pendiente.objects.filter(estado__in=["PENDIENTE", "EN_PROGRESO"]).count(),
        "reparaciones_activas": Reparacion.objects.exclude(estado__in=["CERRADO", "RETIRADO"]).count(),
        "entregas_mes": (
            MovimientoDetalle.objects
            .filter(
                movimiento__tipo="EGRESO",
                item__tipo="TONER",
                movimiento__fecha__month=timezone.now().month,
                movimiento__fecha__year=timezone.now().year,
            )
            .aggregate(total=Sum("cantidad"))["total"] or 0
        ),
    }
    return render(request, "inventario/dashboard.html", {"stats": stats})


@login_required
def diagrama_bd(request):
    return render(request, "inventario/diagrama_bd.html")


@login_required
def reportes_page(request):
    total_entregas = (
        MovimientoDetalle.objects
        .filter(movimiento__tipo="EGRESO", item__tipo="TONER", movimiento__anulado=False)
        .aggregate(total=Sum("cantidad"))["total"] or 0
    )
    return render(request, "inventario/reportes/index.html", {
        "total_entregas_toner": total_entregas,
        "pcs_count":            ActivoPC.objects.filter(activo=True).count(),
        "patrimonios_count":    PatrimonioUnidad.objects.count(),
        "pedidos_pendientes":   Pedido.objects.exclude(estado__in=["ENTREGADO", "CANCELADO"]).count(),
        "servicios":            Servicio.objects.order_by("nombre"),
        "toners":               Toner.objects.filter(activo=True).order_by("nombre"),
        "pedidos_estados":      Pedido.ESTADOS,
    })


def _html_report(title: str, subtitle: str, filters_text: str,
                  summary: list, columns: list, rows: list, foot_row=None) -> str:
    """Genera un reporte HTML standalone listo para imprimir."""
    now = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")

    summary_html = "".join(
        f'<div class="sum-item"><div class="sum-val">{v}</div><div class="sum-lbl">{l}</div></div>'
        for v, l in summary
    )
    th_html    = "".join(f"<th>{c}</th>" for c in columns)
    tbody_html = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    tfoot_html = ""
    if foot_row:
        tfoot_html = "<tfoot><tr>" + "".join(f"<td>{c}</td>" for c in foot_row) + "</tr></tfoot>"
    filters_html = (
        f'<div class="filters"><strong>Período / filtros:</strong> {filters_text}</div>'
        if filters_text else ""
    )

    PRINT_SVG = (
        '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor"'
        ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="6 9 6 2 18 2 18 9"/>'
        '<path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/>'
        '<rect x="6" y="14" width="12" height="8"/></svg>'
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — InventarioHEEP</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',Arial,Helvetica,sans-serif;color:#1a2a3a;background:#fff;padding:28px;font-size:13px}}
.hdr{{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:3px solid #0f2547;padding-bottom:14px;margin-bottom:16px}}
.hdr-left h1{{font-size:22px;font-weight:900;color:#0f2547;letter-spacing:-.3px}}
.hdr-left .sub{{font-size:12px;color:#5a7a9a;margin-top:3px}}
.hdr-right{{text-align:right;font-size:11px;color:#8a9aaa;line-height:1.7}}
.hdr-right strong{{color:#0f2547;font-size:13px}}
.btn-print{{display:inline-flex;align-items:center;gap:6px;background:#0f2547;color:#fff;border:none;border-radius:6px;padding:7px 14px;font-size:12px;font-weight:700;cursor:pointer;margin-bottom:14px}}
.btn-print:hover{{background:#1a3a6e}}
.summary{{display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap}}
.sum-item{{background:#f0f6ff;border:1px solid #c0d4f0;border-radius:7px;padding:10px 16px;min-width:110px}}
.sum-val{{font-size:26px;font-weight:900;color:#0f2547;line-height:1;font-variant-numeric:tabular-nums}}
.sum-lbl{{font-size:10px;color:#6a8aaa;text-transform:uppercase;letter-spacing:.5px;margin-top:3px;font-weight:700}}
.filters{{background:#f5f8ff;border:1px solid #d0dff0;border-radius:6px;padding:7px 12px;margin-bottom:14px;font-size:11.5px;color:#4a6a8a}}
.filters strong{{color:#0f2547}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
thead{{background:#0f2547;color:#fff}}
thead th{{padding:8px 10px;text-align:left;font-weight:700;font-size:10.5px;text-transform:uppercase;letter-spacing:.5px;white-space:nowrap}}
tbody td{{padding:6px 10px;border-bottom:1px solid #e0e8f0;vertical-align:middle}}
tbody tr:nth-child(even){{background:#f5f9ff}}
tfoot td{{padding:8px 10px;background:#deeaff;font-weight:800;border-top:2px solid #0f2547;color:#0f2547}}
.footer{{margin-top:20px;padding-top:10px;border-top:1px solid #d0dce8;font-size:10.5px;color:#8a9aaa;text-align:center}}
@media print{{
  .btn-print{{display:none}}
  body{{padding:14px}}
  thead{{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}}
  tbody tr:nth-child(even){{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}}
  tfoot{{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}}
  .sum-item{{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}}
}}
</style>
</head>
<body>
<div class="hdr">
  <div class="hdr-left">
    <h1>InventarioHEEP</h1>
    <div class="sub">{title}</div>
  </div>
  <div class="hdr-right">
    <strong>{subtitle}</strong><br>
    Generado: {now}
  </div>
</div>
<button class="btn-print" onclick="window.print()">{PRINT_SVG} Imprimir / Guardar PDF</button>
{filters_html}
<div class="summary">{summary_html}</div>
<table>
  <thead><tr>{th_html}</tr></thead>
  <tbody>{tbody_html}</tbody>
  {tfoot_html}
</table>
<div class="footer">InventarioHEEP &nbsp;·&nbsp; Reporte generado el {now}</div>
</body>
</html>"""


def _parse_mes(mes_str: str):
    """Parsea 'YYYY-MM' → (year, month) o (None, None)."""
    if mes_str and len(mes_str) == 7:
        try:
            parts = mes_str.split("-")
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            pass
    return None, None


@login_required
def reporte_toner_html(request):
    mes_str = (request.GET.get("mes") or "").strip()
    year, month = _parse_mes(mes_str)

    qs = (
        MovimientoDetalle.objects
        .select_related("movimiento__servicio", "item__toner")
        .filter(movimiento__tipo="EGRESO", item__tipo="TONER", movimiento__anulado=False)
        .order_by("movimiento__servicio__nombre", "-movimiento__fecha")
    )
    if year and month:
        qs = qs.filter(movimiento__fecha__year=year, movimiento__fecha__month=month)

    rows = []
    total_ud = 0
    for d in qs:
        m = d.movimiento
        t = d.item.toner
        rows.append([
            timezone.localtime(m.fecha).strftime("%d/%m/%Y"),
            m.servicio.nombre if m.servicio else "—",
            t.nombre if t else "—",
            t.marca if t else "—",
            t.modelo_impresora if t else "—",
            d.cantidad,
            (m.observaciones or "").replace("\n", " ").strip() or "—",
        ])
        total_ud += d.cantidad

    periodo = mes_str or "Todos los períodos"
    html = _html_report(
        title    = "Reporte de entregas de tóner",
        subtitle = periodo,
        filters_text = f"Período: {periodo}",
        summary  = [(total_ud, "unidades entregadas"), (len(rows), "movimientos")],
        columns  = ["Fecha", "Servicio", "Tóner", "Marca", "Modelo impresora", "Cantidad", "Observaciones"],
        rows     = rows,
        foot_row = ["Total", "", "", "", "", total_ud, ""],
    )
    fname = f"toner_{mes_str or 'total'}_{timezone.now():%Y%m%d}.html"
    response = HttpResponse(html.encode("utf-8"), content_type="text/html; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{fname}"'
    return response


@login_required
def reporte_pcs_html(request):
    mes_str = (request.GET.get("mes") or "").strip()
    year, month = _parse_mes(mes_str)

    qs = (
        PatrimonioUnidad.objects
        .select_related(
            "pedido_detalle__item__activo_pc",
            "pedido_detalle__item__articulo",
            "pedido_detalle__pedido",
            "servicio_asignado",
        )
        .order_by("servicio_asignado__nombre", "nombre_pc")
    )
    if year and month:
        qs = qs.filter(fecha__year=year, fecha__month=month)

    rows = []
    for p in qs:
        item = p.pedido_detalle.item if p.pedido_detalle else None
        nombre_item = "—"
        if item:
            if item.activo_pc:   nombre_item = item.activo_pc.nombre_pc
            elif item.articulo:  nombre_item = item.articulo.nombre
            elif item.toner:     nombre_item = f"{item.toner.marca} {item.toner.nombre}"
        rows.append([
            p.numero_patrimonio,
            nombre_item,
            p.nombre_pc or "—",
            p.ip or "—",
            p.usuario_asignado or "—",
            p.servicio_asignado.nombre if p.servicio_asignado else "—",
            p.serial or "—",
            p.pedido_detalle.pedido.numero if p.pedido_detalle else "—",
            timezone.localtime(p.fecha).strftime("%d/%m/%Y") if p.fecha else "—",
        ])

    periodo = mes_str or "Todos los períodos"
    html = _html_report(
        title    = "Reporte de equipos y patrimonios",
        subtitle = periodo,
        filters_text = f"Período de alta: {periodo}",
        summary  = [(len(rows), "patrimonios registrados")],
        columns  = ["Nº Patrimonio", "Artículo", "Nombre equipo", "IP", "Usuario asignado",
                    "Servicio asignado", "Serial", "Nº Pedido", "Fecha alta"],
        rows     = rows,
    )
    fname = f"pcs_{mes_str or 'total'}_{timezone.now():%Y%m%d}.html"
    response = HttpResponse(html.encode("utf-8"), content_type="text/html; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{fname}"'
    return response


@login_required
def reporte_pedidos_html(request):
    mes_str     = (request.GET.get("mes") or "").strip()
    estado      = (request.GET.get("estado") or "").strip()
    servicio_id = (request.GET.get("servicio") or "").strip()
    year, month = _parse_mes(mes_str)

    qs = Pedido.objects.select_related("servicio_solicitante", "proveedor").order_by("-creado")
    if year and month:
        qs = qs.filter(creado__year=year, creado__month=month)
    if estado:
        qs = qs.filter(estado=estado)
    if servicio_id:
        try:
            qs = qs.filter(servicio_solicitante_id=int(servicio_id))
        except ValueError:
            pass

    rows = []
    for p in qs:
        rows.append([
            p.numero,
            p.get_estado_display(),
            p.servicio_solicitante.nombre if p.servicio_solicitante else "—",
            p.proveedor.nombre if p.proveedor else "—",
            (p.para_que or "—").replace("\n", " "),
            timezone.localtime(p.creado).strftime("%d/%m/%Y") if p.creado else "—",
            p.fecha_aprobado.strftime("%d/%m/%Y") if p.fecha_aprobado else "—",
            p.fecha_recibido.strftime("%d/%m/%Y") if p.fecha_recibido else "—",
            p.fecha_entregado.strftime("%d/%m/%Y") if p.fecha_entregado else "—",
        ])

    partes = []
    if mes_str:     partes.append(f"Mes: {mes_str}")
    if estado:      partes.append(f"Estado: {estado}")
    if servicio_id: partes.append(f"Servicio ID: {servicio_id}")
    filters_text = " · ".join(partes) if partes else "Todos los pedidos"

    html = _html_report(
        title    = "Reporte de pedidos",
        subtitle = filters_text,
        filters_text = filters_text,
        summary  = [(len(rows), "pedidos")],
        columns  = ["Número", "Estado", "Servicio solicitante", "Proveedor", "Para qué",
                    "Creado", "Aprobado", "Recibido", "Entregado"],
        rows     = rows,
    )
    fname = f"pedidos_{mes_str or 'total'}_{timezone.now():%Y%m%d}.html"
    response = HttpResponse(html.encode("utf-8"), content_type="text/html; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{fname}"'
    return response


@login_required
def reporte_movimientos_html(request):
    mes_str     = (request.GET.get("mes") or "").strip()
    servicio_id = (request.GET.get("servicio") or "").strip()
    year, month = _parse_mes(mes_str)

    qs = (
        MovimientoDetalle.objects
        .select_related(
            "movimiento", "movimiento__servicio",
            "item", "item__toner", "item__articulo",
            "item__activo_pc", "item__impresora",
        )
        .order_by("-movimiento__fecha")
    )
    if year and month:
        qs = qs.filter(movimiento__fecha__year=year, movimiento__fecha__month=month)
    if servicio_id:
        qs = qs.filter(movimiento__servicio_id=servicio_id)

    rows = []
    for d in qs:
        m = d.movimiento
        rows.append([
            timezone.localtime(m.fecha).strftime("%d/%m/%Y %H:%M"),
            m.tipo,
            m.servicio.nombre if m.servicio else "—",
            str(d.item),
            d.cantidad,
            (m.observaciones or "—").replace("\n", " ").strip(),
        ])

    periodo = mes_str or "Todos los períodos"
    partes = [f"Período: {periodo}"]
    if servicio_id:
        partes.append(f"Servicio ID: {servicio_id}")

    html = _html_report(
        title    = "Reporte de movimientos de stock",
        subtitle = periodo,
        filters_text = " · ".join(partes),
        summary  = [(len(rows), "movimientos")],
        columns  = ["Fecha", "Tipo", "Servicio", "Ítem", "Cantidad", "Observaciones"],
        rows     = rows,
    )
    fname = f"movimientos_{mes_str or 'total'}_{timezone.now():%Y%m%d}.html"
    response = HttpResponse(html.encode("utf-8"), content_type="text/html; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{fname}"'
    return response


@login_required
def pcs_reporte_csv(request):
    pats = (
        PatrimonioUnidad.objects
        .select_related(
            "pedido_detalle__item__activo_pc",
            "pedido_detalle__item__articulo",
            "pedido_detalle__item__toner",
            "pedido_detalle__pedido",
            "servicio_asignado",
        )
        .order_by("servicio_asignado__nombre", "nombre_pc")
    )

    buf = io.StringIO()
    buf.write('﻿')
    writer = csv.writer(buf)
    writer.writerow(["Nº Patrimonio", "Artículo", "Nombre equipo", "IP", "Usuario asignado",
                     "Servicio asignado", "Serial", "Nº Pedido"])
    for p in pats:
        item = p.pedido_detalle.item if p.pedido_detalle else None
        nombre_item = ""
        if item:
            if item.activo_pc:
                nombre_item = item.activo_pc.nombre_pc
            elif item.articulo:
                nombre_item = item.articulo.nombre
            elif item.toner:
                nombre_item = f"{item.toner.marca} {item.toner.nombre}"
        writer.writerow([
            p.numero_patrimonio,
            nombre_item,
            p.nombre_pc or "",
            p.ip or "",
            p.usuario_asignado or "",
            p.servicio_asignado.nombre if p.servicio_asignado else "",
            p.serial or "",
            p.pedido_detalle.pedido.numero if p.pedido_detalle else "",
        ])

    content = buf.getvalue().encode("utf-8")
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="reporte_pcs_{timezone.now():%Y%m%d}.csv"'
    return response


@login_required
def pedidos_reporte_csv(request):
    estado      = (request.GET.get("estado") or "").strip()
    servicio_id = (request.GET.get("servicio") or "").strip()
    fecha_desde = (request.GET.get("fecha_desde") or "").strip()
    fecha_hasta = (request.GET.get("fecha_hasta") or "").strip()

    qs = Pedido.objects.select_related("servicio_solicitante", "proveedor").order_by("-creado")

    if estado:
        qs = qs.filter(estado=estado)
    if servicio_id:
        try:
            qs = qs.filter(servicio_solicitante_id=int(servicio_id))
        except ValueError:
            pass
    if fecha_desde:
        try:
            qs = qs.filter(creado__date__gte=datetime.strptime(fecha_desde, "%Y-%m-%d").date())
        except ValueError:
            pass
    if fecha_hasta:
        try:
            qs = qs.filter(creado__date__lte=datetime.strptime(fecha_hasta, "%Y-%m-%d").date())
        except ValueError:
            pass

    buf = io.StringIO()
    buf.write('﻿')
    writer = csv.writer(buf)
    writer.writerow(["Número", "Estado", "Servicio solicitante", "Proveedor", "Para qué",
                     "Creado", "Aprobado", "Recibido", "Entregado"])
    for p in qs:
        writer.writerow([
            p.numero,
            p.get_estado_display(),
            p.servicio_solicitante.nombre if p.servicio_solicitante else "",
            p.proveedor.nombre if p.proveedor else "",
            (p.para_que or "").replace("\n", " "),
            timezone.localtime(p.creado).strftime("%Y-%m-%d") if p.creado else "",
            p.fecha_aprobado.strftime("%Y-%m-%d") if p.fecha_aprobado else "",
            p.fecha_recibido.strftime("%Y-%m-%d") if p.fecha_recibido else "",
            p.fecha_entregado.strftime("%Y-%m-%d") if p.fecha_entregado else "",
        ])

    content = buf.getvalue().encode("utf-8")
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="reporte_pedidos_{timezone.now():%Y%m%d}.csv"'
    return response


### TONER ####
@login_required
def toner_page(request):
    q = (request.GET.get("q") or "").strip()

    toners = Toner.objects.all().order_by("-id")
    if q:
        toners = toners.filter(
            Q(nombre__icontains=q) |
            Q(marca__icontains=q) |
            Q(modelo_impresora__icontains=q)
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
        "toners": page_obj,
        "page_obj": page_obj,
        "movimientos": movimientos,
        "mostrar_ver_todo": mostrar_ver_todo,
    })


@login_required
def toner_list(request):
    q = (request.GET.get("q") or "").strip()
    toners = Toner.objects.all()

    if q:
        toners = toners.filter(
            Q(marca__icontains=q) |
            Q(nombre__icontains=q) |
            Q(modelo_impresora__icontains=q)
        )

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

            with transaction.atomic():
                mov = Movimiento.objects.create(
                    tipo="EGRESO",
                    fecha=fecha,
                    servicio=servicio,
                    observaciones=obs,
                )

                MovimientoDetalle.objects.create(
                    movimiento=mov,
                    item=item_de_toner(toner),
                    cantidad=cantidad,
                )

            return redirect("toner_page")
    else:
        form = EntregaRapidaTonerForm()

    return render(request, "inventario/toner/toner_entrega.html", {"form": form})


@login_required
def toner_create(request):
    if request.method == "POST":
        form = TonerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Toner creado correctamente.")
            return redirect("toner_list")
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

    if q:
        detalles = detalles.filter(
            Q(item__toner__nombre__icontains=q) |
            Q(item__toner__marca__icontains=q) |
            Q(item__toner__modelo_impresora__icontains=q) |
            Q(movimiento__servicio__nombre__icontains=q) |
            Q(movimiento__observaciones__icontains=q)
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


# BACKUP #
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


### ARTICULO ###
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


# PC #
@login_required
def pcs_page(request):
    q = (request.GET.get("q") or "").strip()

    pcs = ActivoPC.objects.select_related("servicio").order_by("-id")
    if q:
        pcs = pcs.filter(
            Q(nombre_pc__icontains=q) |
            Q(ip__icontains=q) |
            Q(patrimonio__icontains=q) |
            Q(serie__icontains=q) |
            Q(servicio__nombre__icontains=q)
        )

    # PCs registradas desde pedidos (patrimonios con nombre de equipo o tipo PC/articulo)
    pats = (
        PatrimonioUnidad.objects
        .select_related(
            "pedido_detalle__item__articulo",
            "pedido_detalle__item__activo_pc",
            "pedido_detalle__pedido",
            "servicio_asignado",
        )
        .order_by("-id")
    )
    if q:
        pats = pats.filter(
            Q(nombre_pc__icontains=q) |
            Q(numero_patrimonio__icontains=q) |
            Q(ip__icontains=q) |
            Q(usuario_asignado__icontains=q) |
            Q(servicio_asignado__nombre__icontains=q) |
            Q(pedido_detalle__item__articulo__nombre__icontains=q)
        )

    paginator_pcs  = Paginator(pcs, 5)
    page_obj       = paginator_pcs.get_page(request.GET.get("page", 1))
    paginator_pats = Paginator(pats, 5)
    page_obj_pats  = paginator_pats.get_page(request.GET.get("page_pat", 1))

    return render(request, "inventario/pcs/pcs.html", {
        "q": q,
        "pcs": page_obj, "page_obj": page_obj,
        "pats": page_obj_pats, "page_obj_pats": page_obj_pats,
    })


@login_required
def pcs_create(request):
    if request.method == "POST":
        form = ActivoPCForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "PC creada.")
            return redirect("pcs_page")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = ActivoPCForm()

    return render(request, "inventario/pcs/pc_form.html", {"form": form, "mode": "create"})


@login_required
def pcs_edit(request, pk):
    pc = get_object_or_404(ActivoPC, pk=pk)

    if request.method == "POST":
        form = ActivoPCForm(request.POST, instance=pc)
        if form.is_valid():
            form.save()
            messages.success(request, "PC actualizada.")
            return redirect("pcs_page")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = ActivoPCForm(instance=pc)

    return render(request, "inventario/pcs/pc_form.html", {"form": form, "mode": "edit", "pc": pc})


# SERVICIOS #
@login_required
def servicios_page(request):
    q = (request.GET.get("q") or "").strip()

    servicios = Servicio.objects.all().order_by("nombre")
    if q:
        servicios = servicios.filter(
            Q(nombre__icontains=q) |
            Q(descripcion__icontains=q)
        )

    paginator = Paginator(servicios, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/servicios/servicios.html", {
        "q": q, "servicios": page_obj, "page_obj": page_obj,
    })


@login_required
def servicio_create(request):
    if request.method == "POST":
        form = ServicioForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Servicio creado.")
            return redirect("servicios_page")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = ServicioForm()

    return render(request, "inventario/servicios/servicio_form.html", {"form": form, "mode": "create"})


@login_required
def servicio_edit(request, pk: int):
    servicio = get_object_or_404(Servicio, pk=pk)

    if request.method == "POST":
        form = ServicioForm(request.POST, instance=servicio)
        if form.is_valid():
            form.save()
            messages.success(request, "Servicio actualizado.")
            return redirect("servicios_page")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = ServicioForm(instance=servicio)

    return render(request, "inventario/servicios/servicio_form.html", {
        "form": form,
        "mode": "edit",
        "servicio": servicio
    })


# IMPRESORA #
@login_required
def impresoras_page(request):
    q = (request.GET.get("q") or "").strip()

    impresoras = (
        Impresora.objects
        .select_related("toner")
        .prefetch_related(
            Prefetch(
                "asignaciones",
                queryset=AsignacionImpresora.objects.select_related("servicio").order_by("-fecha_desde"),
            )
        )
        .order_by("-id")
    )

    if q:
        impresoras = impresoras.filter(
            Q(marca__icontains=q) |
            Q(modelo__icontains=q) |
            Q(patrimonio__icontains=q) |
            Q(ip__icontains=q)
        )

    paginator = Paginator(impresoras, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/impresoras/impresoras.html", {
        "impresoras": page_obj, "page_obj": page_obj, "q": q,
    })


@login_required
def asignar_impresora(request, impresora_id):
    impresora = get_object_or_404(Impresora, id=impresora_id)

    if request.method == "POST":
        form = AsignacionImpresoraForm(request.POST)
        if form.is_valid():
            hoy = timezone.localdate()

            AsignacionImpresora.objects.filter(
                impresora=impresora,
                fecha_hasta__isnull=True
            ).update(fecha_hasta=hoy)

            asignacion = form.save(commit=False)
            asignacion.impresora = impresora
            if not asignacion.fecha_desde:
                asignacion.fecha_desde = hoy
            asignacion.save()

            messages.success(request, f"Impresora asignada a {asignacion.servicio} correctamente.")
            return redirect("impresoras_page")
    else:
        form = AsignacionImpresoraForm(initial={"fecha_desde": timezone.localdate()})

    return render(
        request,
        "inventario/impresoras/asignar_impresora.html",
        {"impresora": impresora, "form": form, "title": "Asignar impresora a servicio"},
    )


@login_required
def impresora_create(request):
    if request.method == "POST":
        form = ImpresoraForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Impresora creada.")
            return redirect("impresoras_page")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = ImpresoraForm()

    return render(request, "inventario/impresoras/impresora_form.html", {"form": form, "mode": "create"})


@login_required
def impresora_edit(request, pk):
    impresora = get_object_or_404(Impresora, pk=pk)

    if request.method == "POST":
        form = ImpresoraForm(request.POST, instance=impresora)
        if form.is_valid():
            form.save()
            messages.success(request, "Impresora actualizada.")
            return redirect("impresoras_page")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = ImpresoraForm(instance=impresora)

    return render(request, "inventario/impresoras/impresora_form.html", {"form": form, "mode": "edit", "impresora": impresora})


@login_required
def impresora_toggle(request, pk):
    impresora = get_object_or_404(Impresora, pk=pk)
    impresora.estado = "INACTIVA" if impresora.estado == "ACTIVA" else "ACTIVA"
    impresora.save(update_fields=["estado"])
    return redirect("impresoras_page")


@login_required
def impresora_entrega(request):
    if request.method == "POST":
        form = EntregaRapidaImpresoraForm(request.POST)
        if form.is_valid():
            servicio = form.cleaned_data["servicio"]
            impresora = form.cleaned_data["impresora"]
            observaciones = (form.cleaned_data.get("observaciones") or "").strip()
            fecha = form.cleaned_data.get("fecha") or timezone.now()

            if is_naive(fecha):
                fecha = make_aware(fecha, timezone.get_current_timezone())

            try:
                with transaction.atomic():
                    movimiento = Movimiento.objects.create(
                        tipo="EGRESO",
                        fecha=fecha,
                        servicio=servicio,
                        observaciones=observaciones,
                    )

                    MovimientoDetalle.objects.create(
                        movimiento=movimiento,
                        item=item_de_impresora(impresora),
                        cantidad=1,
                    )

                messages.success(request, "Movimiento de impresora registrado correctamente.")
                return redirect("impresoras_page")

            except Exception as e:
                messages.error(request, f"Error al registrar movimiento: {e}")
        else:
            messages.error(request, "Revisá los datos del formulario.")
    else:
        form = EntregaRapidaImpresoraForm()

    return render(request, "inventario/impresoras/impresora_entrega.html", {"form": form})


@login_required
def impresora_historial(request):
    q = (request.GET.get("q") or "").strip()

    detalles = (
        MovimientoDetalle.objects
        .select_related("movimiento", "item", "item__impresora", "movimiento__servicio")
        .filter(movimiento__tipo="EGRESO", item__tipo="IMPRESORA")
        .order_by("-movimiento__fecha")
    )

    if q:
        detalles = detalles.filter(
            Q(item__impresora__marca__icontains=q) |
            Q(item__impresora__modelo__icontains=q) |
            Q(movimiento__servicio__nombre__icontains=q) |
            Q(movimiento__observaciones__icontains=q)
        )

    paginator = Paginator(detalles, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/impresoras/impresoras_historial.html", {
        "detalles": page_obj, "page_obj": page_obj, "q": q,
    })


# MOVIMIENTOS #
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


# PRESTAMOS #
@login_required
def prestamos_list(request):
    q = (request.GET.get("q") or "").strip()

    prestamos = (
        Prestamo.objects
        .select_related("servicio")
        .prefetch_related("detalles", "detalles__item")
        .order_by("-fecha_retiro")
    )

    if q:
        prestamos = prestamos.filter(
            Q(servicio__nombre__icontains=q) |
            Q(entregado_a__icontains=q) |
            Q(observaciones__icontains=q) |
            Q(detalles__detalle__icontains=q) |
            Q(detalles__item__tipo__icontains=q)
        ).distinct()

    paginator = Paginator(prestamos, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/prestamos/list.html", {
        "prestamos": page_obj, "page_obj": page_obj, "q": q,
    })


@login_required
def prestamo_create(request):
    if request.method == "POST":
        form = PrestamoForm(request.POST)
        formset = PrestamoDetalleFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                prestamo = form.save()
                formset.instance = prestamo
                formset.save()
            return redirect("prestamos_list")
    else:
        form = PrestamoForm()
        formset = PrestamoDetalleFormSet()

    return render(request, "inventario/prestamos/form.html", {
        "form": form,
        "formset": formset,
    })


@login_required
def prestamo_edit(request, pk):
    prestamo = get_object_or_404(Prestamo, pk=pk)
    if request.method == "POST":
        form = PrestamoForm(request.POST, instance=prestamo)
        formset = PrestamoDetalleFormSet(request.POST, instance=prestamo)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            return redirect("prestamo_detail", pk=prestamo.pk)
    else:
        form = PrestamoForm(instance=prestamo)
        formset = PrestamoDetalleFormSet(instance=prestamo)

    return render(request, "inventario/prestamos/form.html", {
        "form": form,
        "formset": formset,
        "prestamo": prestamo,
    })


@login_required
def prestamo_detail(request, pk):
    prestamo = get_object_or_404(
        Prestamo.objects.select_related("servicio").prefetch_related("detalles", "detalles__item"),
        pk=pk
    )
    return render(request, "inventario/prestamos/detail.html", {"prestamo": prestamo})


@login_required
def prestamo_devolver(request, pk):
    prestamo = get_object_or_404(Prestamo, pk=pk)

    if request.method == "POST":
        prestamo.fecha_devolucion_real = timezone.now()
        prestamo.save(update_fields=["fecha_devolucion_real"])
        messages.success(request, "Préstamo marcado como devuelto.")
        return redirect("prestamo_detail", pk=prestamo.pk)

    return redirect("prestamo_detail", pk=prestamo.pk)


# PENDIENTES #
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
        form = PendienteForm()

    estado_filtro = (request.GET.get("estado") or "").strip()
    pendientes = Pendiente.objects.select_related("servicio").all()
    if estado_filtro:
        pendientes = pendientes.filter(estado=estado_filtro)

    return render(request, "inventario/pendientes/pendientes.html", {
        "form": form,
        "pendientes": pendientes,
        "estado_filtro": estado_filtro,
        "today": timezone.localdate(),
    })


@login_required
@require_POST
def pendiente_toggle(request, pk):
    p = get_object_or_404(Pendiente, pk=pk)
    p.estado = _CICLO_ESTADO.get(p.estado, "PENDIENTE")
    p.save(update_fields=["estado"])
    return redirect("pendientes_page")


@login_required
@require_POST
def pendiente_obs(request, pk):
    p = get_object_or_404(Pendiente, pk=pk)
    p.observacion = (request.POST.get("observacion") or "").strip()
    p.save(update_fields=["observacion"])
    return redirect("pendientes_page")


@login_required
@require_POST
def pendiente_delete(request, pk):
    p = get_object_or_404(Pendiente, pk=pk)
    p.delete()
    return redirect("pendientes_page")


# REPARACIONES #
@login_required
def reparaciones_list(request):
    estado = (request.GET.get("estado") or "").strip()
    q      = (request.GET.get("q") or "").strip()
    reparaciones = Reparacion.objects.select_related("item", "proveedor", "servicio").order_by("-creado")
    if estado:
        reparaciones = reparaciones.filter(estado=estado)
    if q:
        reparaciones = reparaciones.filter(
            Q(proveedor__nombre__icontains=q) |
            Q(diagnostico__icontains=q) |
            Q(seguimiento__icontains=q) |
            Q(servicio__nombre__icontains=q)
        )
    paginator = Paginator(reparaciones, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/reparaciones/reparaciones_list.html", {
        "reparaciones": page_obj, "page_obj": page_obj,
        "estado": estado, "q": q, "estados": Reparacion.ESTADOS,
    })


@login_required
def reparacion_detail(request, pk):
    rep      = get_object_or_404(Reparacion.objects.select_related("item", "proveedor", "servicio"), pk=pk)
    labels   = dict(Reparacion.ESTADOS)
    paso_actual = _PASOS_TIMELINE_REP.index(rep.estado) if rep.estado in _PASOS_TIMELINE_REP else -1
    siguiente   = _SIGUIENTE_ESTADO_REP.get(rep.estado)
    return render(request, "inventario/reparaciones/reparacion_detail.html", {
        "rep":             rep,
        "pasos":           [(v, labels.get(v, v)) for v in _PASOS_TIMELINE_REP],
        "paso_actual":     paso_actual,
        "siguiente":       siguiente,
        "siguiente_label": labels.get(siguiente, "") if siguiente else "",
    })


@login_required
@require_POST
def reparacion_avanzar(request, pk):
    rep       = get_object_or_404(Reparacion, pk=pk)
    siguiente = _SIGUIENTE_ESTADO_REP.get(rep.estado)
    if siguiente:
        rep.estado = siguiente
        rep.save(update_fields=["estado", "actualizado"])
        messages.success(request, f"Reparación avanzada a {rep.get_estado_display()}.")
    return redirect("reparacion_detail", pk=rep.pk)


@login_required
def reparacion_create(request):
    if request.method == "POST":
        form = ReparacionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("reparaciones_list")
    else:
        form = ReparacionForm()

    return render(request, "inventario/reparaciones/reparacion_form.html", {
        "form": form,
        "title": "Nueva reparación",
    })


@login_required
def reparacion_edit(request, pk):
    rep = get_object_or_404(Reparacion, pk=pk)

    if request.method == "POST":
        form = ReparacionForm(request.POST, instance=rep)
        if form.is_valid():
            form.save()
            return redirect("reparaciones_list")
    else:
        form = ReparacionForm(instance=rep)

    return render(request, "inventario/reparaciones/reparacion_form.html", {
        "form": form,
        "title": f"Editar reparación #{rep.id}",
        "rep": rep,
    })


# PEDIDOS #
_SIGUIENTE_ESTADO_PEDIDO = {
    "HECHO":    "APROBADO",
    "APROBADO": "RECIBIDO",
    "RECIBIDO": "ENTREGADO",
}

_PASOS_TIMELINE = ["HECHO", "APROBADO", "RECIBIDO", "ENTREGADO"]


@login_required
def pedidos_list(request):
    q = (request.GET.get("q") or "").strip()
    servicio_id = (request.GET.get("servicio") or "").strip()
    estado = (request.GET.get("estado") or "").strip()

    pedidos = (
        Pedido.objects
        .select_related("servicio_solicitante")
        .order_by("-creado")
    )

    if q:
        pedidos = pedidos.filter(
            Q(numero__icontains=q) |
            Q(numero_nota__icontains=q) |
            Q(para_que__icontains=q) |
            Q(observaciones__icontains=q)
        )

    if servicio_id and servicio_id.lower() != "none":
        try:
            pedidos = pedidos.filter(servicio_solicitante_id=int(servicio_id))
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
        Pedido.objects.select_related("servicio_solicitante"),
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

    return render(request, "inventario/pedidos/detail.html", {
        "pedido":          pedido,
        "detalles":        detalles,
        "siguiente":       siguiente,
        "siguiente_label": labels.get(siguiente, "") if siguiente else "",
        "pasos":           pasos_display,
        "paso_actual":     paso_actual,
        "form":            form,
        "formset":         formset,
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
        if siguiente == "APROBADO"  and not pedido.fecha_aprobado:
            pedido.fecha_aprobado = hoy;  campos.append("fecha_aprobado")
        if siguiente == "RECIBIDO"  and not pedido.fecha_recibido:
            pedido.fecha_recibido = hoy;  campos.append("fecha_recibido")
        if siguiente == "ENTREGADO" and not pedido.fecha_entregado:
            pedido.fecha_entregado = hoy; campos.append("fecha_entregado")
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


@login_required
def patrimonios_list(request):
    q = (request.GET.get("q") or "").strip()
    tipo = request.GET.get("tipo") or ""

    pats = (
        PatrimonioUnidad.objects
        .select_related(
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
            Q(pedido_detalle__item__articulo__nombre__icontains=q) |
            Q(pedido_detalle__item__toner__nombre__icontains=q) |
            Q(pedido_detalle__item__toner__marca__icontains=q) |
            Q(pedido_detalle__item__activo_pc__nombre_pc__icontains=q) |
            Q(pedido_detalle__item__impresora__modelo__icontains=q)
        )

    if tipo:
        pats = pats.filter(pedido_detalle__item__tipo=tipo)

    paginator = Paginator(pats, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/patrimonios/list.html", {
        "pats": page_obj, "page_obj": page_obj, "q": q, "tipo": tipo,
    })


@login_required
def patrimonio_edit(request, pk):
    pat = get_object_or_404(PatrimonioUnidad.objects.select_related("pedido_detalle__pedido"), pk=pk)
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

    return render(request, "inventario/pedidos/patrimonio_form.html", {
        "form": form,
        "detalle": detalle,
        "pedido": pedido,
        "cargados": detalle.patrimonios.count(),
        "maximo": detalle.cantidad,
    })


# NOTA #
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
    "ENVIADA":  "APROBADA",
    "APROBADA": "CERRADA",
}
_PASOS_TIMELINE_NOTA = ["BORRADOR", "ENVIADA", "APROBADA", "CERRADA"]

_SIGUIENTE_ESTADO_REP = {
    "RECIBIDO":      "ENVIADO",
    "ENVIADO":       "EN_REPARACION",
    "EN_REPARACION": "LISTO",
    "LISTO":         "RETIRADO",
    "RETIRADO":      "CERRADO",
}
_PASOS_TIMELINE_REP = ["RECIBIDO", "ENVIADO", "EN_REPARACION", "LISTO", "RETIRADO", "CERRADO"]


@login_required
def nota_list(request):
    q      = (request.GET.get("q") or "").strip()
    estado = (request.GET.get("estado") or "").strip()
    notas  = Nota.objects.select_related("servicio_solicitante").order_by("-fecha", "-creado")
    if q:
        notas = notas.filter(
            Q(numero__icontains=q) |
            Q(servicio_solicitante__nombre__icontains=q) |
            Q(detalle__icontains=q)
        )
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
    return render(request, "inventario/notas/detalle.html", {
        "nota":            nota,
        "detalles":        detalles,
        "pasos":           [(v, labels.get(v, v)) for v in _PASOS_TIMELINE_NOTA],
        "paso_actual":     paso_actual,
        "siguiente":       siguiente,
        "siguiente_label": labels.get(siguiente, "") if siguiente else "",
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


@login_required
def busqueda_global(request):
    q = (request.GET.get("q") or "").strip()
    if not q:
        return redirect("dashboard")

    toners = Toner.objects.filter(
        Q(nombre__icontains=q) | Q(marca__icontains=q) | Q(modelo_impresora__icontains=q)
    ).order_by("marca", "nombre")[:12]

    articulos = Articulo.objects.filter(
        Q(nombre__icontains=q) | Q(marca__icontains=q) | Q(descripcion__icontains=q)
    ).order_by("nombre")[:12]

    pcs = ActivoPC.objects.select_related("servicio").filter(
        Q(nombre_pc__icontains=q) | Q(ip__icontains=q) |
        Q(patrimonio__icontains=q) | Q(serie__icontains=q)
    ).order_by("nombre_pc")[:12]

    impresoras = Impresora.objects.filter(
        Q(marca__icontains=q) | Q(modelo__icontains=q) |
        Q(patrimonio__icontains=q) | Q(ip__icontains=q)
    ).order_by("marca", "modelo")[:12]

    servicios = Servicio.objects.filter(
        Q(nombre__icontains=q) | Q(descripcion__icontains=q)
    ).order_by("nombre")[:12]

    total = toners.count() + articulos.count() + pcs.count() + impresoras.count() + servicios.count()

    return render(request, "inventario/busqueda.html", {
        "q": q,
        "toners": toners,
        "articulos": articulos,
        "pcs": pcs,
        "impresoras": impresoras,
        "servicios": servicios,
        "total": total,
    })


def handler_404(request, exception):
    return render(request, "404.html", status=404)


def handler_500(request):
    return render(request, "500.html", status=500)


# =====================================
# PANEL DE ADMINISTRACIÓN (superadmin)
# =====================================
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import user_passes_test
from .forms.admin_forms import UsuarioCreateForm, UsuarioEditForm, RolForm

solo_superadmin = user_passes_test(lambda u: u.is_superuser, login_url="/accounts/login/")


@login_required
@solo_superadmin
def admin_panel(request):
    User = get_user_model()
    total_usuarios = User.objects.count()
    total_activos = User.objects.filter(is_active=True).count()
    total_roles = Group.objects.count()
    return render(request, "inventario/admin/panel.html", {
        "total_usuarios": total_usuarios,
        "total_activos": total_activos,
        "total_roles": total_roles,
    })


@login_required
@solo_superadmin
def admin_usuarios(request):
    User = get_user_model()
    usuarios = User.objects.prefetch_related("groups").order_by("-is_superuser", "-is_staff", "username")
    return render(request, "inventario/admin/usuarios.html", {"usuarios": usuarios})


@login_required
@solo_superadmin
def admin_usuario_create(request):
    form = UsuarioCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Usuario creado correctamente.")
        return redirect("admin_usuarios")
    return render(request, "inventario/admin/usuario_form.html", {"form": form, "titulo": "Nuevo usuario"})


@login_required
@solo_superadmin
def admin_usuario_edit(request, pk):
    User = get_user_model()
    usuario = get_object_or_404(User, pk=pk)
    form = UsuarioEditForm(request.POST or None, instance=usuario)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Usuario '{usuario.username}' actualizado.")
        return redirect("admin_usuarios")
    return render(request, "inventario/admin/usuario_form.html", {
        "form": form,
        "titulo": f"Editar usuario — {usuario.username}",
        "usuario": usuario,
    })


@login_required
@solo_superadmin
@require_POST
def admin_usuario_toggle(request, pk):
    User = get_user_model()
    usuario = get_object_or_404(User, pk=pk)
    if usuario == request.user:
        messages.error(request, "No podés desactivar tu propia cuenta.")
        return redirect("admin_usuarios")
    usuario.is_active = not usuario.is_active
    usuario.save(update_fields=["is_active"])
    estado = "activado" if usuario.is_active else "desactivado"
    messages.success(request, f"Usuario '{usuario.username}' {estado}.")
    return redirect("admin_usuarios")


@login_required
@solo_superadmin
@require_POST
def admin_usuario_delete(request, pk):
    User = get_user_model()
    usuario = get_object_or_404(User, pk=pk)
    if usuario == request.user:
        messages.error(request, "No podés eliminar tu propia cuenta.")
        return redirect("admin_usuarios")
    nombre = usuario.username
    usuario.delete()
    messages.success(request, f"Usuario '{nombre}' eliminado.")
    return redirect("admin_usuarios")


@login_required
@solo_superadmin
def admin_roles(request):
    roles = Group.objects.prefetch_related("user_set").order_by("name")
    return render(request, "inventario/admin/roles.html", {"roles": roles})


@login_required
@solo_superadmin
def admin_rol_create(request):
    form = RolForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Rol creado correctamente.")
        return redirect("admin_roles")
    return render(request, "inventario/admin/rol_form.html", {"form": form, "titulo": "Nuevo rol"})


@login_required
@solo_superadmin
def admin_rol_edit(request, pk):
    rol = get_object_or_404(Group, pk=pk)
    form = RolForm(request.POST or None, instance=rol)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Rol '{rol.name}' actualizado.")
        return redirect("admin_roles")
    return render(request, "inventario/admin/rol_form.html", {
        "form": form,
        "titulo": f"Editar rol — {rol.name}",
        "rol": rol,
    })


@login_required
@solo_superadmin
@require_POST
def admin_rol_delete(request, pk):
    rol = get_object_or_404(Group, pk=pk)
    nombre = rol.name
    rol.delete()
    messages.success(request, f"Rol '{nombre}' eliminado.")
    return redirect("admin_roles")
