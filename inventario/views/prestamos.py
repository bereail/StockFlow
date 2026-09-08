from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from ..models import Prestamo, Servicio
from ..forms.prestamos import PrestamoForm, PrestamoDetalleFormSet
from ..services.listados import ordenar


@login_required
def prestamos_list(request):
    q = (request.GET.get("q") or "").strip()
    servicio_id = (request.GET.get("servicio") or "").strip()
    estado = (request.GET.get("estado") or "").strip()

    prestamos = (
        Prestamo.objects
        .select_related("servicio")
        .prefetch_related("detalles", "detalles__item")
    )

    if q:
        prestamos = prestamos.filter(
            Q(servicio__nombre__icontains=q) |
            Q(entregado_a__icontains=q) |
            Q(observaciones__icontains=q) |
            Q(detalles__detalle__icontains=q) |
            Q(detalles__item__tipo__icontains=q)
        ).distinct()
    if servicio_id:
        prestamos = prestamos.filter(servicio_id=servicio_id)
    if estado == "activo":
        prestamos = prestamos.filter(fecha_devolucion_real__isnull=True)
    elif estado == "devuelto":
        prestamos = prestamos.filter(fecha_devolucion_real__isnull=False)

    prestamos, sort_actual, dir_actual = ordenar(
        request, prestamos,
        campos={"fecha": "fecha_retiro", "servicio": "servicio__nombre", "entregado_a": "entregado_a"},
        default="fecha",
        direccion_default="desc",
    )

    paginator = Paginator(prestamos, 5)
    page_obj  = paginator.get_page(request.GET.get("page", 1))
    return render(request, "inventario/prestamos/list.html", {
        "prestamos": page_obj, "page_obj": page_obj, "q": q,
        "servicio_id": servicio_id, "estado": estado,
        "servicios": Servicio.objects.order_by("nombre"),
        "sort_actual": sort_actual, "dir_actual": dir_actual,
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
