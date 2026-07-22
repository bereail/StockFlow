from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from ..models import Servicio
from ..forms.servicios import ServicioForm


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
