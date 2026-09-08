from django.conf import settings
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from ..models import (
    Toner,
    Articulo,
    Servicio,
    ActivoPC,
    Impresora,
    Movimiento,
    MovimientoDetalle,
    Pendiente,
    Reparacion,
    Prestamo,
    Intercambio,
)
from ..services.stock import toners_con_stock_critico


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
                # En el ejecutable de escritorio es una sola persona en su propio
                # equipo: conviene no pedirle login en cada apertura.
                dias = 90 if getattr(settings, "FROZEN", False) else 14
                request.session.set_expiry(60 * 60 * 24 * dias)
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
        "intercambios_pendientes": Intercambio.objects.filter(estado="PENDIENTE").count(),
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

    movimientos_recientes = (
        Movimiento.objects
        .filter(anulado=False)
        .select_related("servicio")
        .prefetch_related(
            "detalles__item__toner",
            "detalles__item__articulo",
            "detalles__item__activo_pc",
            "detalles__item__impresora",
        )
        .order_by("-fecha")[:6]
    )

    return render(request, "inventario/dashboard.html", {
        "stats": stats,
        "stock_critico": toners_con_stock_critico(),
        "movimientos_recientes": movimientos_recientes,
    })


@login_required
def diagrama_bd(request):
    return render(request, "inventario/diagrama_bd.html")


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
