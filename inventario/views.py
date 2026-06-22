import csv
from django.forms import formset_factory, modelformset_factory
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Prefetch
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
    Pedido, PedidoDetalle,
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
from .forms.prestamos import PrestamoForm
from .forms.pendientes import PendienteForm
from .forms.reparaciones import ReparacionForm
from .forms.pedidos import PedidoForm, PedidoDetalleFormSet, PatrimonioUnidadForm
from .forms.asignaciones import AsignacionImpresoraForm
from .forms.nota import NotaForm, NotaDetalleFormSet
from .services.items import item_de_toner, item_de_articulo, item_de_impresora


@login_required
def dashboard(request):
    return render(request, "inventario/dashboard.html")


### TONER ####
@login_required
def toner_page(request):
    q = (request.GET.get("q") or "").strip()

    toners = Toner.objects.all().order_by("marca", "nombre")
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
        .order_by("-movimiento__fecha")[:4]
    )

    movimientos = list(movimientos_qs)
    mostrar_ver_todo = len(movimientos) > 3
    movimientos = movimientos[:3]

    return render(request, "inventario/toner/toner.html", {
        "q": q,
        "toners": toners,
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

    return render(request, "inventario/toner/toner_list.html", {
        "toners": toners,
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

    return render(request, "inventario/toner/toner_historial.html", {"detalles": detalles, "q": q})


# BACKUP #
@login_required
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

    return render(request, "inventario/articulos/articulos.html", {
        "q": q,
        "articulos": articulos,
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

    return render(request, "inventario/articulos/articulos_historial.html", {"detalles": detalles, "q": q})


# PC #
@login_required
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

    return render(request, "inventario/pcs/pcs.html", {"q": q, "pcs": pcs})


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

    return render(request, "inventario/servicios/servicios.html", {
        "q": q,
        "servicios": servicios,
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
        .order_by("marca", "modelo")
    )

    if q:
        impresoras = impresoras.filter(
            Q(marca__icontains=q) |
            Q(modelo__icontains=q) |
            Q(patrimonio__icontains=q) |
            Q(ip__icontains=q)
        )

    return render(
        request,
        "inventario/impresoras/impresoras.html",
        {
            "impresoras": impresoras,
            "q": q,
        },
    )


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

    return render(request, "inventario/impresoras/impresoras_historial.html", {"detalles": detalles, "q": q})


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

    return render(request, "inventario/movimientos/movimientos_list.html", {
        "movimientos": movimientos[:200],
        "servicios": servicios,
        "toners": toners,
        "filtros": filtros,
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

    return render(request, "inventario/prestamos/list.html", {
        "prestamos": prestamos,
        "q": q,
    })


@login_required
def prestamo_create(request):
    if request.method == "POST":
        form = PrestamoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("prestamos_list")
    else:
        form = PrestamoForm()

    return render(request, "inventario/prestamos/form.html", {"form": form})


@login_required
def prestamo_edit(request, pk):
    prestamo = get_object_or_404(Prestamo, pk=pk)

    if request.method == "POST":
        form = PrestamoForm(request.POST, instance=prestamo)
        if form.is_valid():
            form.save()
            return redirect("prestamos_list")
    else:
        form = PrestamoForm(instance=prestamo)

    return render(request, "inventario/prestamos/form.html", {"form": form, "prestamo": prestamo})


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
@login_required
def pendientes_page(request):
    form = PendienteForm()

    if request.method == "POST":
        form = PendienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("pendientes_page")

    pendientes = Pendiente.objects.select_related("servicio").all()
    return render(request, "inventario/pendientes/pendientes.html", {
        "form": form,
        "pendientes": pendientes,
    })


@login_required
@require_POST
def pendiente_toggle(request, pk):
    p = get_object_or_404(Pendiente, pk=pk)
    p.completado = not p.completado
    p.save(update_fields=["completado"])
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
    q = (request.GET.get("q") or "").strip()

    reparaciones = Reparacion.objects.select_related("item", "proveedor").all()

    if estado:
        reparaciones = reparaciones.filter(estado=estado)

    if q:
        reparaciones = reparaciones.filter(
            Q(proveedor__nombre__icontains=q) |
            Q(diagnostico__icontains=q) |
            Q(seguimiento__icontains=q)
        )

    return render(request, "inventario/reparaciones/reparaciones_list.html", {
        "reparaciones": reparaciones,
        "estado": estado,
        "q": q,
        "estados": Reparacion.ESTADOS,
    })


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

    return render(request, "inventario/pedidos/list.html", {
        "pedidos": pedidos,
        "q": q,
        "servicio_id": servicio_id if servicio_id.lower() != "none" else "",
        "estado": estado,
        "estados": Pedido.ESTADOS,
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

    if pedido.estado not in ("HECHO",):
        messages.error(request, "Este pedido no se puede editar en este estado.")
        return redirect("pedido_detail", pk=pedido.pk)

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

    return render(request, "inventario/pedidos/detail.html", {
        "pedido": pedido,
        "detalles": detalles,
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


@login_required
def nota_list(request):
    notas = Nota.objects.select_related("servicio_solicitante").all()
    return render(request, "inventario/notas/lista.html", {"notas": notas})


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
    nota = get_object_or_404(Nota.objects.select_related("servicio_solicitante"), pk=pk)
    detalles = nota.detalles.select_related("item").all()
    return render(request, "inventario/notas/detalle.html", {"nota": nota, "detalles": detalles})
