from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from ..models import ActivoPC, PatrimonioUnidad, Reparacion, Servicio
from ..forms.pcs import ActivoPCForm
from ..services.items import item_de_pc
from ..services.listados import ordenar


@login_required
def pcs_page(request):
    q = (request.GET.get("q") or "").strip()
    servicio_id = (request.GET.get("servicio") or "").strip()

    pcs = ActivoPC.objects.select_related("servicio")
    if q:
        pcs = pcs.filter(
            Q(nombre_pc__icontains=q) |
            Q(ip__icontains=q) |
            Q(patrimonio__icontains=q) |
            Q(serie__icontains=q) |
            Q(servicio__nombre__icontains=q)
        )
    if servicio_id:
        pcs = pcs.filter(servicio_id=servicio_id)

    pcs, sort_actual, dir_actual = ordenar(
        request, pcs,
        campos={"nombre": "nombre_pc", "ip": "ip", "servicio": "servicio__nombre", "estado": "activo"},
        default="nombre",
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
        "servicio_id": servicio_id,
        "servicios": Servicio.objects.order_by("nombre"),
        "sort_actual": sort_actual,
        "dir_actual": dir_actual,
        "pcs": page_obj, "page_obj": page_obj,
        "pats": page_obj_pats, "page_obj_pats": page_obj_pats,
    })


@login_required
def pc_detail(request, pk):
    pc = get_object_or_404(ActivoPC.objects.select_related("servicio", "impresora", "articulo"), pk=pk)
    item = item_de_pc(pc)
    reparaciones = (
        Reparacion.objects
        .filter(item=item)
        .select_related("proveedor")
        .order_by("-creado")
    )
    return render(request, "inventario/pcs/pc_detail.html", {
        "pc": pc,
        "reparaciones": reparaciones,
    })


@login_required
def pcs_create(request):
    next_url = request.GET.get("next") or request.POST.get("next") or ""

    if request.method == "POST":
        form = ActivoPCForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "PC creada.")
            return redirect(next_url or "pcs_page")
        messages.error(request, "Revisá los errores del formulario.")
    else:
        servicio_id = request.GET.get("servicio")
        form = ActivoPCForm(initial={"servicio": servicio_id} if servicio_id else None)

    return render(request, "inventario/pcs/pc_form.html", {
        "form": form, "mode": "create", "next": next_url,
    })


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
