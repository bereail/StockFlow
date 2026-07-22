from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from ..models import ActivoPC, PatrimonioUnidad
from ..forms.pcs import ActivoPCForm


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
