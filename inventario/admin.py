from django.contrib import admin
from .models import (
    Toner,
    Articulo,
    Servicio,
    Impresora,
    Movimiento,
    MovimientoDetalle,
    Item,
    Proveedor,
    Prestamo,
    PrestamoDetalle,
    ItemComponente
)

# =========================
# TONER
# =========================
@admin.register(Toner)
class TonerAdmin(admin.ModelAdmin):
    list_display = ("id", "marca", "nombre", "modelo_impresora", "activo")
    search_fields = ("marca", "nombre", "modelo_impresora")
    list_filter = ("activo",)


# =========================
# MODELOS SIMPLES
# =========================
admin.site.register(Articulo)
admin.site.register(Servicio)
admin.site.register(Impresora)


# =========================
# ITEM (con PRÉSTAMOS)
# =========================
class ItemComponenteInline(admin.TabularInline):
    model = ItemComponente
    fk_name = "item_padre"
    extra = 1

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "item_hijo":
            qs = Item.objects.all()

            # ✅ Regla: el componente NO puede ser TONER
            qs = qs.exclude(tipo="TONER")

            # ✅ (recomendado) Evitar combos dentro de combos
            qs = qs.filter(es_combo=False)

            kwargs["queryset"] = qs

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("id", "tipo", "es_combo", "prestable", "categoria_prestamo")
    list_filter = ("tipo", "es_combo", "prestable", "categoria_prestamo")
    search_fields = ("id",)
    list_editable = ("es_combo", "prestable", "categoria_prestamo")

    inlines = [ItemComponenteInline]
# =========================
# PRESTAMOS (GENÉRICO)
# =========================
class PrestamoDetalleInline(admin.TabularInline):
    model = PrestamoDetalle
    extra = 0


@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = (
    "id", "servicio", "fecha_retiro", "fecha_devolucion_estimada", "fecha_devolucion_real",
    "proyector", "camara_web", "prolongacion", "notebook",
    "telefono_contacto",
    )
    list_filter = ("fecha_devolucion_real", "servicio", "proyector", "camara_web", "prolongacion", "notebook")

    search_fields = ("servicio__nombre", "telefono_contacto", "entregado_a", "observaciones")
    ordering = ("-fecha_retiro",)
    inlines = [PrestamoDetalleInline]


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


# =========================
# PROVEEDORES
# =========================
@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ("nombre", "telefono", "email", "activo")
    search_fields = ("nombre", "telefono", "email")
    list_filter = ("activo",)
    ordering = ("nombre",)

