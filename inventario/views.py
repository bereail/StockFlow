import os
import csv
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.db.models import Q, F
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404

from .models import Toner, Movimiento, Servicio
from .forms import TonerForm, MovimientoForm




def dashboard(request):
    q = (request.GET.get("q") or "").strip()
    toners = Toner.objects.all()
    if q:
        toners = toners.filter(
            Q(marca__icontains=q) | Q(modelo__icontains=q) | Q(codigo__icontains=q)
        )
    toners = toners.order_by("marca", "modelo")

    movimientos = Movimiento.objects.select_related("toner", "servicio")[:20]
    stock_bajo = Toner.objects.filter(minimo__gt=0, stock__lte=F("minimo")).order_by("stock")[:50]


    return render(request, "inventario/dashboard.html", {
    "toners": toners,
    "movimientos": movimientos,
    "stock_bajo": stock_bajo,
    "q": q,
})


def toner_new(request):
    if request.method == "POST":
        form = TonerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Toner creado.")
            return redirect("dashboard")
    else:
        form = TonerForm()
    return render(request, "inventario/toner_form.html", {"form": form, "title": "Nuevo Toner"})

def movimiento_new(request):
    initial = {}
    toner_q = request.GET.get("toner")
    if toner_q:
        initial["toner"] = toner_q

    if request.method == "POST":
        form = MovimientoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Movimiento registrado y stock actualizado.")
            return redirect("dashboard")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = MovimientoForm(initial=initial)

    return render(request, "inventario/movimiento_form.html", {"form": form, "title": "Nuevo Movimiento"})

def servicios(request):
    # mini pantalla para cargar servicios rápido
    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        if nombre:
            Servicio.objects.get_or_create(nombre=nombre)
            messages.success(request, "Servicio guardado.")
            return redirect("servicios")
        messages.error(request, "Nombre requerido.")

    lista = Servicio.objects.order_by("nombre")
    return render(request, "inventario/servicios.html", {"servicios": lista})


def movimiento_anular(request, mov_id):
    mov = get_object_or_404(Movimiento, id=mov_id)

    if mov.anulado:
        messages.info(request, "Este movimiento ya fue anulado.")
        return redirect("movimientos_list")

    if request.method == "POST":
        motivo = (request.POST.get("motivo") or "").strip()

        try:
            # crear contramovimiento
            if mov.tipo == "EGRESO":
                nuevo = Movimiento(
                    toner=mov.toner,
                    tipo="INGRESO",
                    cantidad=mov.cantidad,
                    entregado_a="ANULACIÓN",
                    observaciones=f"Anula movimiento #{mov.id}. Motivo: {motivo}"
                )
            else:  # INGRESO
                nuevo = Movimiento(
                    toner=mov.toner,
                    tipo="EGRESO",
                    cantidad=mov.cantidad,
                    servicio=mov.servicio,
                    entregado_a="ANULACIÓN",
                    observaciones=f"Anula movimiento #{mov.id}. Motivo: {motivo}"
                )

            nuevo.save()  # ← aplica stock automáticamente

            mov.anulado = True
            mov.anulado_motivo = motivo
            mov.save(update_fields=["anulado", "anulado_motivo"])

            messages.success(request, "Movimiento anulado correctamente.")
        except Exception as e:
            messages.error(request, f"No se pudo anular: {e}")

        return redirect("movimientos_list")

    return render(request, "inventario/movimiento_anular.html", {"mov": mov})


def movimientos_list(request):
    tipo = request.GET.get("tipo", "")
    toner_id = request.GET.get("toner", "")
    servicio_id = request.GET.get("servicio", "")
    desde = request.GET.get("desde", "")
    hasta = request.GET.get("hasta", "")

    movimientos = Movimiento.objects.select_related(
        "toner", "servicio"
    ).order_by("-fecha")

    if tipo:
        movimientos = movimientos.filter(tipo=tipo)

    if toner_id:
        movimientos = movimientos.filter(toner_id=toner_id)

    if servicio_id:
        movimientos = movimientos.filter(servicio_id=servicio_id)

    if desde:
        movimientos = movimientos.filter(fecha__date__gte=desde)

    if hasta:
        movimientos = movimientos.filter(fecha__date__lte=hasta)

    toners = Toner.objects.order_by("marca", "modelo")
    servicios = Servicio.objects.order_by("nombre")

    return render(request, "inventario/movimientos_list.html", {
        "movimientos": movimientos[:500],  # límite sano
        "toners": toners,
        "servicios": servicios,
        "filtros": {
            "tipo": tipo,
            "toner": toner_id,
            "servicio": servicio_id,
            "desde": desde,
            "hasta": hasta,
        }
    })



def movimientos_export_csv(request):
    # mismos filtros que movimientos_list
    tipo = request.GET.get("tipo", "")
    toner_id = request.GET.get("toner", "")
    servicio_id = request.GET.get("servicio", "")
    desde = request.GET.get("desde", "")
    hasta = request.GET.get("hasta", "")

    qs = Movimiento.objects.select_related("toner", "servicio").order_by("-fecha")

    if tipo:
        qs = qs.filter(tipo=tipo)
    if toner_id:
        qs = qs.filter(toner_id=toner_id)
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
        "fecha", "tipo", "marca", "modelo", "codigo", "cantidad",
        "servicio", "entregado_a", "observaciones", "anulado", "anulado_motivo"
    ])

    for m in qs:
        writer.writerow([
            m.fecha.strftime("%Y-%m-%d %H:%M:%S"),
            m.tipo,
            m.toner.marca,
            m.toner.modelo,
            m.toner.codigo,
            m.cantidad,
            m.servicio.nombre if m.servicio else "",
            m.entregado_a or "",
            (m.observaciones or "").replace("\n", " ").strip(),
            "SI" if getattr(m, "anulado", False) else "NO",
            getattr(m, "anulado_motivo", "") or "",
        ])

    return response

def _get_backups_dir():
    appdata_dir = os.path.dirname(str(settings.DATABASES["default"]["NAME"]))  # ...\StockToner
    backups_dir = os.path.join(appdata_dir, "backups")
    os.makedirs(backups_dir, exist_ok=True)
    return backups_dir


def abrir_backups(request):
    try:
        backups_dir = _get_backups_dir()
        os.startfile(backups_dir)  # Windows Explorer

        messages.success(request, "Carpeta de backups abierta.")
    except Exception as e:
        messages.error(request, f"No se pudo abrir la carpeta de backups: {e}")

    return redirect("dashboard")
