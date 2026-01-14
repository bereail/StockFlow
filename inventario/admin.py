from django.contrib import admin
from .models import (
    Toner,
    Articulo,
    Servicio,
    Impresora,
    PrestamoProyector,
    Movimiento,
    MovimientoDetalle,
    Item,
)


class TonerAdmin(admin.ModelAdmin):
    list_display = ("id", "marca", "nombre", "modelo_impresora", "activo")
    search_fields = ("marca", "nombre", "modelo_impresora")
    list_filter = ("activo",)
# =========================
# MODELOS SIMPLES
# =========================
admin.site.register(Toner)
admin.site.register(Articulo)
admin.site.register(Servicio)
admin.site.register(Impresora)
admin.site.register(Item)

# =========================
# PROYECTOR
# =========================
@admin.register(PrestamoProyector)
class PrestamoProyectorAdmin(admin.ModelAdmin):
    list_display = (
        "servicio",
        "fecha_retiro",
        "fecha_devolucion_estimada",
        "fecha_devolucion_real",
        "telefono_contacto",
    )
    list_filter = ("fecha_devolucion_real", "servicio")
    search_fields = ("servicio__nombre", "telefono_contacto")
    ordering = ("-fecha_retiro",)

# =========================
# MOVIMIENTOS
# =========================
class MovimientoDetalleInline(admin.TabularInline):
    model = MovimientoDetalle
    extra = 0

@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ("tipo", "fecha", "servicio", "anulado")
    list_filter = ("tipo", "anulado", "servicio")
    search_fields = ("servicio__nombre", "observaciones")
    inlines = [MovimientoDetalleInline]
    ordering = ("-fecha",)