from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
import csv
from django.contrib import messages
from .models import Toner, Item, Movimiento, MovimientoDetalle, Articulo, Servicio, ActivoPC, Impresora, PrestamoProyector, Pendiente
from .forms import TonerForm, EntregaRapidaTonerForm, ArticuloForm, EntregaRapidaArticuloForm, ServicioForm, ActivoPCForm, ImpresoraForm, EntregaRapidaImpresoraForm, PrestamoProyectorForm, PendienteForm
from django.utils.timezone import is_naive, make_aware
from django.views.decorators.http import require_POST


def dashboard(request):
    return render(request, "inventario/dashboard.html")


  ### TONER ####
def toner_page(request):
    q = (request.GET.get("q") or "").strip()

    toners = Toner.objects.all().order_by("marca", "nombre")
    if q:
        toners = toners.filter(
            Q(nombre__icontains=q) |
            Q(marca__icontains=q) |
            Q(modelo_impresora__icontains=q)
        )

    # Últimos EGRESOS de toner
    movimientos = (MovimientoDetalle.objects
        .select_related("movimiento", "item", "item__toner", "movimiento__servicio")
        .filter(movimiento__tipo="EGRESO", item__tipo="TONER")
        .order_by("-movimiento__fecha")[:10]
    )

    return render(request, "inventario/toner.html", {
        "q": q,
        "toners": toners,
        "movimientos": movimientos,
    })

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

    return render(request, "inventario/toner_list.html", {
        "toners": toners,
        "q": q,
        "title": "Toners",
    })


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

            # Unificamos "entregado_a" dentro de observaciones sin tocar el form
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

                item, _ = Item.objects.get_or_create(
                    tipo="TONER",
                    toner=toner,
                    defaults={"articulo": None, "activo_pc": None},
                )

                MovimientoDetalle.objects.create(
                    movimiento=mov,
                    item=item,
                    cantidad=cantidad,
                )

            return redirect("toner_page")
    else:
        form = EntregaRapidaTonerForm()

    return render(request, "inventario/toner_entrega.html", {"form": form})


def toner_create(request):
    if request.method == "POST":
        form = TonerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Toner creado correctamente.")
            return redirect("toner_list")  # o "toner_page"
        else:
            messages.error(request, "❌ Revisá el formulario, hay errores.")
    else:
        form = TonerForm()

    return render(request, "inventario/toner_form.html", {"form": form, "mode": "create"})

def toner_edit(request, pk: int):
    toner = get_object_or_404(Toner, pk=pk)

    if request.method == "POST":
        form = TonerForm(request.POST, instance=toner)
        if form.is_valid():
            form.save()
            return redirect("toner_page")
    else:
        form = TonerForm(instance=toner)

    return render(request, "inventario/toner_form.html", {"form": form, "mode": "edit", "toner": toner})


def toner_toggle(request, pk: int):
    toner = get_object_or_404(Toner, pk=pk)
    toner.activo = not toner.activo
    toner.save(update_fields=["activo"])
    return redirect("toner_page")


def toner_historial(request):
    q = (request.GET.get("q") or "").strip()

    detalles = (MovimientoDetalle.objects
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

    return render(request, "inventario/toner_historial.html", {"detalles": detalles, "q": q})


# BACKUP #
def backup_entregas_csv(request):
    detalles = (MovimientoDetalle.objects
        .select_related("movimiento", "item", "item__toner", "movimiento__servicio", "movimiento__documento")
        .filter(movimiento__tipo="EGRESO", item__tipo="TONER")
        .order_by("-movimiento__fecha")
    )

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="entregas_toner.csv"'

    writer = csv.writer(response)
    writer.writerow(["fecha", "servicio", "toner", "marca", "modelo_impresora", "cantidad", "documento", "observaciones"])

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

    return response

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
def articulos_page(request):
    q = (request.GET.get("q") or "").strip()

    articulos = Articulo.objects.all().order_by("marca", "nombre")
    if q:
        articulos = articulos.filter(
            Q(nombre__icontains=q) |
            Q(marca__icontains=q) |
            Q(descripcion__icontains=q)
        )

    return render(request, "inventario/articulos.html", {
        "q": q,
        "articulos": articulos,
    })


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

    return render(request, "inventario/articulo_form.html", {"form": form, "mode": "create"})


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

    return render(request, "inventario/articulo_form.html", {
        "form": form,
        "mode": "edit",
        "articulo": articulo
    })


def articulo_toggle(request, pk: int):
    articulo = get_object_or_404(Articulo, pk=pk)
    articulo.activo = not articulo.activo
    articulo.save(update_fields=["activo"])
    return redirect("articulos_page")

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

                item, _ = Item.objects.get_or_create(
                    tipo="ARTICULO",
                    articulo=articulo,
                    defaults={"toner": None, "activo_pc": None},
                )

                MovimientoDetalle.objects.create(
                    movimiento=mov,
                    item=item,
                    cantidad=cantidad,
                )

            return redirect("articulos_page")
    else:
        form = EntregaRapidaArticuloForm()

    return render(request, "inventario/articulo_entrega.html", {"form": form})


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

    return render(request, "inventario/articulos_historial.html", {"detalles": detalles, "q": q})



# PC #


def pcs_page(request):
    q = (request.GET.get("q") or "").strip()

    pcs = ActivoPC.objects.select_related("servicio").order_by("nombre_pc")
    if q:
        pcs = pcs.filter(
            Q(nombre_pc__icontains=q) |
            Q(ip__icontains=q) |
            Q(patrimonio__icontains=q) |
            Q(serie__icontains=q) |
            Q(servicio__nombre__icontains=q)
        )

    return render(request, "inventario/pcs.html", {"q": q, "pcs": pcs})


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

    return render(request, "inventario/pc_form.html", {"form": form, "mode": "create"})


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

    return render(request, "inventario/pc_form.html", {"form": form, "mode": "edit", "pc": pc})



# SERVICIOS #

def servicios_page(request):
    q = (request.GET.get("q") or "").strip()

    servicios = Servicio.objects.all().order_by("nombre")
    if q:
        servicios = servicios.filter(
            Q(nombre__icontains=q) |
            Q(descripcion__icontains=q)
        )

    return render(request, "inventario/servicios.html", {
        "q": q,
        "servicios": servicios,
    })


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

    # igual a toner_form.html: usa mode
    return render(request, "inventario/servicio_form.html", {"form": form, "mode": "create"})


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

    return render(request, "inventario/servicio_form.html", {
        "form": form,
        "mode": "edit",
        "servicio": servicio
    })


# IMPRESORA #
def impresoras_page(request):
    q = (request.GET.get("q") or "").strip()

    impresoras = (
        Impresora.objects
        .select_related("servicio", "toner")
        .order_by("marca", "modelo")
    )

    if q:
        impresoras = impresoras.filter(
            Q(marca__icontains=q) |
            Q(modelo__icontains=q) |
            Q(patrimonio__icontains=q) |
            Q(ip__icontains=q) |
            Q(servicio__nombre__icontains=q)
        )

    return render(request, "inventario/impresoras.html", {"impresoras": impresoras, "q": q})


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

    return render(request, "inventario/impresora_form.html", {"form": form, "mode": "create"})


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

    return render(request, "inventario/impresora_form.html", {"form": form, "mode": "edit", "impresora": impresora})


def impresora_toggle(request, pk):
    impresora = get_object_or_404(Impresora, pk=pk)
    impresora.estado = "INACTIVA" if impresora.estado == "ACTIVA" else "ACTIVA"
    impresora.save(update_fields=["estado"])
    return redirect("impresoras_page")


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

                    item, _ = Item.objects.get_or_create(
                        tipo="IMPRESORA",
                        impresora=impresora,
                        defaults={"toner": None, "articulo": None, "activo_pc": None},
                    )

                    MovimientoDetalle.objects.create(
                        movimiento=movimiento,
                        item=item,
                        cantidad=1,
                    )

                    # actualizar servicio asignado
                    impresora.servicio = servicio
                    impresora.save(update_fields=["servicio"])

                messages.success(request, "Movimiento de impresora registrado correctamente.")
                return redirect("impresoras_page")

            except Exception as e:
                messages.error(request, f"Error al registrar movimiento: {e}")
        else:
            messages.error(request, "Revisá los datos del formulario.")
    else:
        form = EntregaRapidaImpresoraForm()

    return render(request, "inventario/impresora_entrega.html", {"form": form})


def impresora_historial(request):
    """Listado simple de movimientos (EGRESO) de impresoras."""
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

    return render(request, "inventario/impresoras_historial.html", {"detalles": detalles, "q": q})


# MOVIMIENTOS #
from django.db.models import Q
from .models import Movimiento, Servicio, Toner

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

    return render(request, "inventario/movimientos_list.html", {
        "movimientos": movimientos[:200],
        "servicios": servicios,
        "toners": toners,
        "filtros": filtros,
    })


# PROYECTOR #
def proyector_prestamos_page(request):
    q = (request.GET.get("q") or "").strip()

    prestamos = PrestamoProyector.objects.select_related("servicio").order_by("-fecha_retiro")

    if q:
        prestamos = prestamos.filter(servicio__nombre__icontains=q)

    return render(request, "inventario/proyector_prestamos.html", {
        "prestamos": prestamos,
        "q": q,
    })

def proyector_prestamo_create(request):
    if request.method == "POST":
        form = PrestamoProyectorForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("proyector_prestamos_page")
    else:
        form = PrestamoProyectorForm(initial={"fecha_retiro": timezone.now()})

    return render(request, "inventario/proyector_prestamo_form.html", {"form": form})

def proyector_prestamo_devolver(request, pk):
    p = get_object_or_404(PrestamoProyector, pk=pk)
    if request.method == "POST":
        p.fecha_devolucion_real = timezone.now()
        p.save()
    return redirect("proyector_prestamos_page")


# PENDIENTES #
def pendientes_page(request):
    form = PendienteForm()

    if request.method == "POST":
        form = PendienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("pendientes_page")

    pendientes = Pendiente.objects.select_related("servicio").all()
    return render(request, "inventario/pendientes.html", {
        "form": form,
        "pendientes": pendientes,
    })


@require_POST
def pendiente_toggle(request, pk):
    p = get_object_or_404(Pendiente, pk=pk)
    p.completado = not p.completado
    p.save(update_fields=["completado"])
    return redirect("pendientes_page")


@require_POST
def pendiente_delete(request, pk):
    p = get_object_or_404(Pendiente, pk=pk)
    p.delete()
    return redirect("pendientes_page")