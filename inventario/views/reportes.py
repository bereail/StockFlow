import csv
import io
from collections import OrderedDict
from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.html import escape as esc
from ..models import Toner, Servicio, ActivoPC, MovimientoDetalle, Pedido, PatrimonioUnidad


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


_RPT_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:14px}
body{
  font-family:'Segoe UI',-apple-system,BlinkMacSystemFont,Arial,sans-serif;
  color:#1e2d3d;background:#fff;padding:32px 40px;line-height:1.55;
  -webkit-font-smoothing:antialiased;
}
/* ─── Header ─── */
.rpt-hdr{
  display:flex;justify-content:space-between;align-items:flex-start;
  gap:20px;border-bottom:3px solid #0f2547;padding-bottom:18px;margin-bottom:22px;
}
.rpt-brand{display:flex;align-items:center;gap:14px}
.rpt-icon{
  width:46px;height:46px;border-radius:12px;flex-shrink:0;
  background:linear-gradient(135deg,#0f2547 0%,#2d5fb3 100%);
  display:flex;align-items:center;justify-content:center;
}
.rpt-icon svg{width:24px;height:24px;stroke:#fff;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.rpt-names .org{font-size:10.5px;color:#7a9ab8;font-weight:700;text-transform:uppercase;letter-spacing:.9px}
.rpt-names .title{font-size:21px;font-weight:900;color:#0f2547;line-height:1.2;margin-top:3px}
.rpt-meta{text-align:right;flex-shrink:0;font-size:11.5px;color:#7a9ab8;line-height:1.8}
.rpt-meta .period{font-size:13px;font-weight:800;color:#0f2547;display:block;margin-bottom:2px}
/* ─── Acciones ─── */
.rpt-actions{display:flex;gap:8px;margin-bottom:18px}
.btn-print{
  display:inline-flex;align-items:center;gap:7px;
  background:#0f2547;color:#fff;border:none;border-radius:7px;
  padding:9px 18px;font-size:13px;font-weight:700;cursor:pointer;letter-spacing:.1px;
}
.btn-print:hover{background:#1a3a6e}
.btn-print svg{width:15px;height:15px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
/* ─── Filtros ─── */
.rpt-filters{
  display:flex;align-items:center;flex-wrap:wrap;gap:6px 12px;
  background:#f2f7ff;border:1px solid #c8daf0;border-radius:7px;
  padding:9px 14px;margin-bottom:18px;font-size:12px;color:#3a5a7a;
}
.rpt-filters b{color:#0f2547;font-weight:800}
/* ─── Resumen ─── */
.rpt-summary{display:flex;gap:12px;margin-bottom:22px;flex-wrap:wrap}
.sum{
  flex:1;min-width:110px;
  background:#f2f7ff;border:1px solid #c8daf0;border-radius:8px;
  padding:12px 18px;border-left:4px solid #0f2547;
}
.sum-val{
  font-size:30px;font-weight:900;color:#0f2547;line-height:1;
  font-variant-numeric:tabular-nums;margin-bottom:5px;
}
.sum-lbl{font-size:10.5px;color:#7a9ab8;font-weight:700;text-transform:uppercase;letter-spacing:.5px}
/* ─── Secciones agrupadas ─── */
.rpt-group{margin-bottom:26px;page-break-inside:avoid}
.rpt-group-hdr{
  display:flex;justify-content:space-between;align-items:center;
  background:#0f2547;color:#fff;
  padding:8px 14px;border-radius:7px 7px 0 0;
  font-size:13px;font-weight:800;letter-spacing:.1px;
}
.rpt-group-hdr .grp-badge{
  background:rgba(255,255,255,.18);border-radius:5px;
  padding:2px 11px;font-size:13.5px;font-weight:900;letter-spacing:.5px;
}
/* ─── Tablas ─── */
table{width:100%;border-collapse:collapse;font-size:13px;border:1px solid #d0e0ef}
.rpt-group table{border-radius:0 0 7px 7px;overflow:hidden;border-top:none}
thead{background:#e6eff8}
thead th{
  padding:9px 12px;text-align:left;font-weight:800;font-size:11px;
  text-transform:uppercase;letter-spacing:.5px;color:#2a4a6a;
  white-space:nowrap;border-bottom:2px solid #c0d4e8;
}
tbody td{
  padding:9px 12px;border-bottom:1px solid #eaf0f8;
  vertical-align:middle;color:#2a3a4a;
}
tbody tr:last-child td{border-bottom:none}
tbody tr:nth-child(even){background:#f6f9fd}
tbody tr:hover{background:#ebf3ff}
/* ─── Subtotales ─── */
tr.subtotal td{
  background:#d8eaff!important;font-weight:800;color:#0f2547;
  border-top:2px solid #b0ccf0;padding:8px 12px;font-size:12.5px;
}
tr.grand-total td{
  background:#0f2547!important;color:#fff!important;
  font-weight:900;font-size:14px;padding:10px 12px;
}
/* ─── Badges de estado ─── */
.badge-estado{
  display:inline-block;padding:2px 9px;border-radius:99px;
  font-size:11px;font-weight:800;white-space:nowrap;
}
.est-HECHO{background:#fff3cd;color:#856404}
.est-APROBADO{background:#cff4fc;color:#055160}
.est-RECIBIDO{background:#d1e7dd;color:#0a3622}
.est-ENTREGADO{background:#d1fae5;color:#065f46}
.est-CANCELADO{background:#f8d7da;color:#842029}
.tipo-INGRESO{background:#d1fae5;color:#065f46}
.tipo-EGRESO{background:#fee2e2;color:#991b1b}
.tipo-AJUSTE{background:#fef9c3;color:#854d0e}
/* ─── Pie ─── */
.rpt-footer{
  margin-top:24px;padding-top:12px;
  border-top:1px solid #d0dce8;
  display:flex;justify-content:space-between;
  font-size:11px;color:#8a9aaa;
}
/* ─── Impresión ─── */
@media print{
  body{padding:16px 20px}
  .rpt-actions{display:none}
  .rpt-group{page-break-inside:avoid}
  thead,.rpt-group-hdr,.sum,tbody tr:nth-child(even),tr.subtotal,tr.grand-total,
  .badge-estado{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}
  @page{margin:1.5cm}
}
"""


_RPT_ICON_SVG = (
    '<svg viewBox="0 0 24 24">'
    '<rect x="6" y="2" width="12" height="8" rx="1"/>'
    '<path d="M4 10h16a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2z"/>'
    '<rect x="7" y="16" width="10" height="6" rx="1"/>'
    '</svg>'
)


_PRINT_SVG = (
    '<svg viewBox="0 0 24 24">'
    '<polyline points="6 9 6 2 18 2 18 9"/>'
    '<path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/>'
    '<rect x="6" y="14" width="12" height="8"/>'
    '</svg>'
)


def _rpt_open(title: str, periodo: str, now: str) -> str:
    return (
        f'<!DOCTYPE html><html lang="es"><head>'
        f'<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{esc(title)} — StockFlow</title>'
        f'<style>{_RPT_CSS}</style></head><body>'
        f'<div class="rpt-hdr">'
        f'  <div class="rpt-brand">'
        f'    <div class="rpt-icon">{_RPT_ICON_SVG}</div>'
        f'    <div class="rpt-names"><div class="org">StockFlow</div>'
        f'    <div class="title">{esc(title)}</div></div>'
        f'  </div>'
        f'  <div class="rpt-meta"><span class="period">{esc(periodo)}</span>Generado: {esc(now)}</div>'
        f'</div>'
        f'<div class="rpt-actions">'
        f'<button class="btn-print" onclick="window.print()">{_PRINT_SVG} Imprimir / Guardar PDF</button>'
        f'</div>'
    )


def _rpt_summary(*items) -> str:
    parts = "".join(
        f'<div class="sum"><div class="sum-val">{v}</div><div class="sum-lbl">{l}</div></div>'
        for v, l in items
    )
    return f'<div class="rpt-summary">{parts}</div>'


def _rpt_filters(text: str) -> str:
    return f'<div class="rpt-filters"><b>Filtros:</b> {esc(text)}</div>' if text else ""


def _rpt_close(now: str) -> str:
    return (
        f'<div class="rpt-footer">'
        f'<span>StockFlow — Sistema de inventario</span>'
        f'<span>Generado: {now}</span>'
        f'</div></body></html>'
    )


def _rpt_table(columns: list, rows: list, foot_row=None) -> str:
    th = "".join(f"<th>{c}</th>" for c in columns)
    td_rows = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    foot = ""
    if foot_row:
        foot = "<tfoot><tr class='grand-total'>" + "".join(f"<td>{c}</td>" for c in foot_row) + "</tr></tfoot>"
    return f"<table><thead><tr>{th}</tr></thead><tbody>{td_rows}</tbody>{foot}</table>"


def _parse_mes(mes_str: str):
    if mes_str and len(mes_str) == 7:
        try:
            y, m = mes_str.split("-")
            return int(y), int(m)
        except (ValueError, AttributeError):
            pass
    return None, None


def _periodo_now(mes_str: str):
    periodo = mes_str or "Todos los períodos"
    now = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")
    return periodo, now


def _html_report_response(body: str, prefix: str, mes_str: str) -> HttpResponse:
    fname = f"{prefix}_{mes_str or 'total'}_{timezone.now():%Y%m%d}.html"
    response = HttpResponse(body.encode("utf-8"), content_type="text/html; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{fname}"'
    return response


def _nombre_item_patrimonio(item) -> str:
    if not item:
        return ""
    if item.activo_pc:
        return item.activo_pc.nombre_pc
    if item.articulo:
        return item.articulo.nombre
    if item.toner:
        return f"{item.toner.marca} {item.toner.nombre}"
    return ""


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

    # Agrupar por servicio
    grupos: dict = OrderedDict()
    total_ud = 0
    for d in qs:
        svc = d.movimiento.servicio.nombre if d.movimiento.servicio else "Sin servicio"
        grupos.setdefault(svc, []).append(d)
        total_ud += d.cantidad

    periodo, now = _periodo_now(mes_str)

    body = _rpt_open("Entregas de tóner por servicio", periodo, now)
    body += _rpt_filters(f"Período: {periodo}" if mes_str else "")
    body += _rpt_summary((total_ud, "unidades entregadas"), (len(grupos), "servicios"), (sum(len(v) for v in grupos.values()), "movimientos"))

    if grupos:
        for svc_nombre, detalles in grupos.items():
            sub = sum(d.cantidad for d in detalles)
            rows_html = ""
            for d in detalles:
                m = d.movimiento
                t = d.item.toner
                rows_html += (
                    "<tr>"
                    f"<td>{timezone.localtime(m.fecha).strftime('%d/%m/%Y')}</td>"
                    f"<td><b>{esc(t.nombre) if t else '—'}</b></td>"
                    f"<td>{esc(t.marca) if t else '—'}</td>"
                    f"<td>{esc(t.modelo_impresora) if t else '—'}</td>"
                    f"<td style='text-align:right;font-weight:700;font-size:15px'>{d.cantidad}</td>"
                    f"<td style='color:#7a9ab8;font-size:12px'>{esc((m.observaciones or '').replace(chr(10),' ').strip()) or '—'}</td>"
                    "</tr>"
                )
            rows_html += (
                f"<tr class='subtotal'>"
                f"<td colspan='4'><b>Subtotal — {esc(svc_nombre)}</b></td>"
                f"<td style='text-align:right'>{sub}</td><td></td></tr>"
            )
            body += (
                f'<div class="rpt-group">'
                f'<div class="rpt-group-hdr"><span>{esc(svc_nombre)}</span>'
                f'<span class="grp-badge">{sub} ud.</span></div>'
                f'<table><thead><tr>'
                f'<th>Fecha</th><th>Tóner</th><th>Marca</th><th>Modelo impresora</th>'
                f'<th style="text-align:right">Cant.</th><th>Observaciones</th>'
                f'</tr></thead><tbody>{rows_html}</tbody></table></div>'
            )
        body += (
            f'<table style="margin-top:10px;border-radius:7px;overflow:hidden">'
            f'<tbody><tr class="grand-total">'
            f'<td colspan="5"><b>TOTAL GENERAL</b></td>'
            f'<td style="text-align:right;font-size:18px;letter-spacing:.5px">{total_ud} ud.</td>'
            f'</tr></tbody></table>'
        )
    else:
        body += '<p style="color:#7a9ab8;padding:24px 0;text-align:center">Sin datos para el período seleccionado.</p>'

    body += _rpt_close(now)
    return _html_report_response(body, "toner", mes_str)


@login_required
def reporte_pcs_html(request):
    mes_str = (request.GET.get("mes") or "").strip()
    year, month = _parse_mes(mes_str)

    qs = (
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
    if year and month:
        qs = qs.filter(fecha__year=year, fecha__month=month)

    grupos: dict = OrderedDict()
    for p in qs:
        svc = p.servicio_asignado.nombre if p.servicio_asignado else "Sin servicio asignado"
        grupos.setdefault(svc, []).append(p)

    periodo, now = _periodo_now(mes_str)
    total = sum(len(v) for v in grupos.values())

    body = _rpt_open("Equipos y patrimonios", periodo, now)
    body += _rpt_filters(f"Período de alta: {periodo}" if mes_str else "")
    body += _rpt_summary((total, "patrimonios"), (len(grupos), "servicios"))

    if grupos:
        for svc_nombre, pats in grupos.items():
            rows_html = ""
            for p in pats:
                item = p.pedido_detalle.item if p.pedido_detalle else None
                nombre_item = _nombre_item_patrimonio(item) or "—"
                rows_html += (
                    "<tr>"
                    f"<td><b>{esc(p.numero_patrimonio or '—')}</b></td>"
                    f"<td>{esc(nombre_item or '—')}</td>"
                    f"<td>{esc(p.nombre_pc or '—')}</td>"
                    f"<td style='font-family:monospace'>{esc(p.ip or '—')}</td>"
                    f"<td>{esc(p.usuario_asignado or '—')}</td>"
                    f"<td>{esc(p.serial or '—')}</td>"
                    f"<td>{esc(p.pedido_detalle.pedido.numero) if p.pedido_detalle else '—'}</td>"
                    f"<td>{timezone.localtime(p.fecha).strftime('%d/%m/%Y') if p.fecha else '—'}</td>"
                    "</tr>"
                )
            body += (
                f'<div class="rpt-group">'
                f'<div class="rpt-group-hdr"><span>{esc(svc_nombre)}</span>'
                f'<span class="grp-badge">{len(pats)} equipo{"s" if len(pats)!=1 else ""}</span></div>'
                f'<table><thead><tr>'
                f'<th>Nº Patrimonio</th><th>Artículo</th><th>Nombre equipo</th>'
                f'<th>IP</th><th>Usuario</th><th>Serial</th><th>Nº Pedido</th><th>Fecha alta</th>'
                f'</tr></thead><tbody>{rows_html}</tbody></table></div>'
            )
    else:
        body += '<p style="color:#7a9ab8;padding:24px 0;text-align:center">Sin patrimonios registrados.</p>'

    body += _rpt_close(now)
    return _html_report_response(body, "pcs", mes_str)


@login_required
def reporte_pedidos_html(request):
    mes_str     = (request.GET.get("mes") or "").strip()
    estado      = (request.GET.get("estado") or "").strip()
    servicio_id = (request.GET.get("servicio") or "").strip()
    year, month = _parse_mes(mes_str)

    qs = Pedido.objects.prefetch_related("servicios").select_related("proveedor").order_by("-creado")
    if year and month:
        qs = qs.filter(creado__year=year, creado__month=month)
    if estado:
        qs = qs.filter(estado=estado)
    if servicio_id:
        try:
            qs = qs.filter(servicios__id=int(servicio_id)).distinct()
        except ValueError:
            pass

    rows = []
    for p in qs:
        est_badge = f'<span class="badge-estado est-{esc(p.estado)}">{esc(p.get_estado_display())}</span>'
        rows.append([
            f"<b>{esc(p.numero)}</b>",
            est_badge,
            esc(", ".join(s.nombre for s in p.servicios.all())) or "—",
            esc(p.proveedor.nombre) if p.proveedor else "—",
            esc((p.para_que or "—").replace("\n", " ")),
            timezone.localtime(p.creado).strftime("%d/%m/%Y") if p.creado else "—",
            p.fecha_aprobado.strftime("%d/%m/%Y") if p.fecha_aprobado else "—",
            p.fecha_recibido.strftime("%d/%m/%Y") if p.fecha_recibido else "—",
            p.fecha_entregado.strftime("%d/%m/%Y") if p.fecha_entregado else "—",
        ])

    partes = []
    if mes_str:     partes.append(f"Mes: {mes_str}")
    if estado:      partes.append(f"Estado: {estado}")
    filters_text = " · ".join(partes) if partes else ""

    periodo, now = _periodo_now(mes_str)

    body = _rpt_open("Reporte de pedidos", periodo, now)
    body += _rpt_filters(filters_text)
    body += _rpt_summary((len(rows), "pedidos"))
    body += _rpt_table(
        columns  = ["Número", "Estado", "Servicio solicitante", "Proveedor", "Para qué",
                    "Creado", "Aprobado", "Recibido", "Entregado"],
        rows     = rows,
        foot_row = [f"Total: {len(rows)} pedidos", "", "", "", "", "", "", "", ""],
    )
    body += _rpt_close(now)
    return _html_report_response(body, "pedidos", mes_str)


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
        tipo_badge = f'<span class="badge-estado tipo-{esc(m.tipo)}">{esc(m.tipo)}</span>'
        rows.append([
            timezone.localtime(m.fecha).strftime("%d/%m/%Y %H:%M"),
            tipo_badge,
            esc(m.servicio.nombre) if m.servicio else "—",
            esc(str(d.item)),
            f"<b>{d.cantidad}</b>",
            esc((m.observaciones or "—").replace("\n", " ").strip()),
        ])

    periodo, now = _periodo_now(mes_str)
    partes = ([f"Período: {mes_str}"] if mes_str else [])

    body = _rpt_open("Movimientos de stock", periodo, now)
    body += _rpt_filters(" · ".join(partes))
    body += _rpt_summary((len(rows), "movimientos"))
    body += _rpt_table(
        columns  = ["Fecha", "Tipo", "Servicio", "Ítem", "Cant.", "Observaciones"],
        rows     = rows,
        foot_row = [f"Total: {len(rows)} movimientos", "", "", "", "", ""],
    )
    body += _rpt_close(now)
    return _html_report_response(body, "movimientos", mes_str)


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
        nombre_item = _nombre_item_patrimonio(item)
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

    qs = Pedido.objects.prefetch_related("servicios").select_related("proveedor").order_by("-creado")

    if estado:
        qs = qs.filter(estado=estado)
    if servicio_id:
        try:
            qs = qs.filter(servicios__id=int(servicio_id)).distinct()
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
    writer.writerow(["Número", "Estado", "Servicios", "Proveedor", "Para qué",
                     "Creado", "Aprobado", "Recibido", "Entregado"])
    for p in qs:
        writer.writerow([
            p.numero,
            p.get_estado_display(),
            ", ".join(s.nombre for s in p.servicios.all()),
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
