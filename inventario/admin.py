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
    ItemComponente,
    Intercambio,
    Pedido,
    PedidoDetalle,
    Nota,
    Reparacion,
    PatrimonioUnidad,
    ActivoPC,
    AsignacionImpresora,
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
    list_display = ("id", "tipo", "es_combo", "prestable")
    list_filter = ("tipo", "es_combo", "prestable")
    search_fields = ("id",)
    list_editable = ("es_combo", "prestable")

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
        "id", "servicio", "entregado_a",
        "fecha_retiro", "fecha_devolucion_estimada", "fecha_devolucion_real",
        "telefono_contacto",
    )
    list_filter = ("fecha_devolucion_real", "servicio")
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
# INTERCAMBIOS
# =========================
@admin.register(Intercambio)
class IntercambioAdmin(admin.ModelAdmin):
    list_display = (
        "id", "servicio_afectado", "servicio_beneficiario",
        "estado", "fecha_intercambio", "fecha_resolucion",
    )
    list_filter = ("estado", "servicio_afectado", "servicio_beneficiario")
    search_fields = ("detalle_saliente", "detalle_entrante", "motivo")
    ordering = ("-fecha_intercambio",)


# =========================
# PROVEEDORES
# =========================
@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ("nombre", "telefono", "email", "activo")
    search_fields = ("nombre", "telefono", "email")
    list_filter = ("activo",)
    ordering = ("nombre",)


# =========================
# ENTIDADES TRANSACCIONALES (ARQ-05)
# Solo vía de contingencia manual si la UI custom fallara — el flujo
# normal sigue siendo la UI propia, que valida reglas de negocio que
# estos ModelAdmin no reproducen (máquinas de estado, stock, etc.).
# =========================
class PedidoDetalleInline(admin.TabularInline):
    model = PedidoDetalle
    extra = 0


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("numero", "estado", "proveedor", "nota", "creado")
    list_filter = ("estado", "proveedor")
    search_fields = ("numero", "observaciones", "para_que")
    ordering = ("-creado",)
    inlines = [PedidoDetalleInline]


@admin.register(Nota)
class NotaAdmin(admin.ModelAdmin):
    list_display = ("numero", "servicio_solicitante", "estado", "fecha")
    list_filter = ("estado", "servicio_solicitante")
    search_fields = ("numero", "detalle")
    ordering = ("-fecha",)


@admin.register(Reparacion)
class ReparacionAdmin(admin.ModelAdmin):
    list_display = ("id", "item", "estado", "servicio", "proveedor", "fecha_envio", "fecha_retorno")
    list_filter = ("estado", "servicio", "proveedor")
    search_fields = ("diagnostico", "seguimiento")
    ordering = ("-creado",)


@admin.register(PatrimonioUnidad)
class PatrimonioUnidadAdmin(admin.ModelAdmin):
    list_display = ("numero_patrimonio", "articulo", "servicio_asignado", "es_donacion", "fecha")
    list_filter = ("es_donacion", "servicio_asignado")
    search_fields = ("numero_patrimonio", "nombre_pc", "ip", "serial", "usuario_asignado")
    ordering = ("-fecha",)


@admin.register(ActivoPC)
class ActivoPCAdmin(admin.ModelAdmin):
    list_display = ("nombre_pc", "ip", "usuario", "articulo")
    search_fields = ("nombre_pc", "ip", "usuario")


@admin.register(AsignacionImpresora)
class AsignacionImpresoraAdmin(admin.ModelAdmin):
    list_display = ("impresora", "servicio", "fecha_desde", "fecha_hasta", "responsable")
    list_filter = ("servicio",)
    search_fields = ("ubicacion", "responsable")
    ordering = ("-fecha_desde",)

