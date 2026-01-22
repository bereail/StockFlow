
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.db.models import Q
from django.conf import settings
from django.core.validators import MinValueValidator

# =========================
# MAESTROS / CATÁLOGOS
# =========================
class Servicio(models.Model):
    """
    Sector/servicio del hospital (ej: Terapia Intensiva).
    """
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Toner(models.Model):
    """
    Catálogo de toners.
    """
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)
    marca = models.CharField(max_length=100, blank=True)
    modelo_impresora = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["nombre", "marca"]

    def __str__(self):
        # Evita "CE285A ()" cuando no hay marca
        return f"{self.nombre}" + (f" ({self.marca})" if self.marca else "")


class Articulo(models.Model):
    """
    Catálogo de artículos (insumos varios).
    """
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    marca = models.CharField(max_length=100, blank=True)
    caracteristicas = models.TextField(blank=True)
    observaciones = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class ActivoPC(models.Model):
    """
    Activos de informática (PCs, etc).
    """
    nombre_pc = models.CharField(max_length=100)
    ip = models.GenericIPAddressField(protocol="IPv4", blank=True, null=True)
    patrimonio = models.CharField(max_length=100, blank=True)
    serie = models.CharField(max_length=100, blank=True)
    caracteristicas = models.TextField(blank=True)
    observaciones = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    # Servicio opcional (puede no estar asignado)
    servicio = models.ForeignKey(
        Servicio, on_delete=models.SET_NULL, null=True, blank=True, related_name="activos_pc"
    )

    class Meta:
        ordering = ["nombre_pc"]

    def __str__(self):
        return self.nombre_pc


class Impresora(models.Model):
    """
    Impresoras del sistema.
    """
    TIPO_CONEXION = (
        ("IP", "Red"),
        ("USB", "USB"),
    )

    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)

    # 'tipo' te lo dejo, pero ojo: es muy genérico.
    # Si lo usás para "Laser / Inkjet / Multifunción", conviene choices.
    tipo = models.CharField(max_length=100)

    patrimonio = models.CharField(max_length=100, blank=True)

    activo = models.BooleanField(default=True)
    estado = models.CharField(max_length=50, default="ACTIVA")

    servicio = models.ForeignKey(
        Servicio, on_delete=models.SET_NULL, null=True, blank=True, related_name="impresoras"
    )

    conexion = models.CharField(max_length=10, choices=TIPO_CONEXION)
    ip = models.GenericIPAddressField(protocol="IPv4", blank=True, null=True)

    toner = models.ForeignKey(
        Toner, on_delete=models.SET_NULL, null=True, blank=True, related_name="impresoras"
    )

    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["marca", "modelo"]

    def __str__(self):
        return f"{self.marca} {self.modelo}"

    def clean(self):
        """
        Validación básica: si la conexión es IP, debería tener IP.
        """
        from django.core.exceptions import ValidationError

        if self.conexion == "IP" and not self.ip:
            raise ValidationError({"ip": "Si la conexión es por red (IP), debés cargar la IP."})


# =========================
# DOCUMENTOS
# =========================
class Documento(models.Model):
    """
    Documento asociado a un movimiento (pedido, nota, orden, etc).
    """
    TIPO_DOCUMENTO = (
        ("PEDIDO", "Pedido"),
        ("NOTA", "Nota"),
        ("ORDEN", "Orden de Provisión"),
    )

    tipo = models.CharField(max_length=20, choices=TIPO_DOCUMENTO)
    numero = models.CharField(max_length=100)
    fecha = models.DateField(default=timezone.now)
    observaciones = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tipo", "numero"], name="uniq_documento_tipo_numero")
        ]
        ordering = ["-fecha", "tipo", "numero"]

    def __str__(self):
        return f"{self.tipo} Nº {self.numero}"


# =========================
# ITEM (POLIMÓRFICO)
# =========================
class Item(models.Model):
    """
    Unifica distintas entidades como "Item" para movimientos:
    - TONER
    - ARTICULO
    - ACTIVO_PC
    - IMPRESORA

    Regla: según 'tipo', SOLO 1 FK debe estar seteada.
    """
    TIPO_CHOICES = [
        ("TONER", "Toner"),
        ("ARTICULO", "Artículo"),
        ("ACTIVO_PC", "Activo PC"),
        ("IMPRESORA", "Impresora"),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)

    # IMPORTANTE:
    # Usamos PROTECT para NO romper históricos (movimientos) si alguien intenta borrar un catálogo.
    toner = models.ForeignKey(Toner, null=True, blank=True, on_delete=models.PROTECT)
    articulo = models.ForeignKey(Articulo, null=True, blank=True, on_delete=models.PROTECT)
    activo_pc = models.ForeignKey(ActivoPC, null=True, blank=True, on_delete=models.PROTECT)
    impresora = models.ForeignKey(Impresora, null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            # Asegura 1 sola FK seteada (XOR simple a nivel DB)
            models.CheckConstraint(
                check=(
                    (Q(toner__isnull=False) & Q(articulo__isnull=True) & Q(activo_pc__isnull=True) & Q(impresora__isnull=True)) |
                    (Q(toner__isnull=True) & Q(articulo__isnull=False) & Q(activo_pc__isnull=True) & Q(impresora__isnull=True)) |
                    (Q(toner__isnull=True) & Q(articulo__isnull=True) & Q(activo_pc__isnull=False) & Q(impresora__isnull=True)) |
                    (Q(toner__isnull=True) & Q(articulo__isnull=True) & Q(activo_pc__isnull=True) & Q(impresora__isnull=False))
                ),
                name="chk_item_exactamente_un_fk",
            ),

            # Evita duplicados por tipo+objeto
            models.UniqueConstraint(
                fields=["tipo", "toner"],
                condition=Q(toner__isnull=False),
                name="uniq_item_toner",
            ),
            models.UniqueConstraint(
                fields=["tipo", "articulo"],
                condition=Q(articulo__isnull=False),
                name="uniq_item_articulo",
            ),
            models.UniqueConstraint(
                fields=["tipo", "activo_pc"],
                condition=Q(activo_pc__isnull=False),
                name="uniq_item_activo_pc",
            ),
            models.UniqueConstraint(
                fields=["tipo", "impresora"],
                condition=Q(impresora__isnull=False),
                name="uniq_item_impresora",
            ),
        ]

    def __str__(self):
        if self.toner:
            return f"TONER: {self.toner}"
        if self.articulo:
            return f"ARTICULO: {self.articulo}"
        if self.activo_pc:
            return f"ACTIVO_PC: {self.activo_pc}"
        if self.impresora:
            return f"IMPRESORA: {self.impresora}"
        return f"Item #{self.pk}"


# =========================
# MOVIMIENTOS
# =========================
class Movimiento(models.Model):
    """
    Movimiento de stock: Ingreso / Egreso / Ajuste.
    Puede estar asociado a un servicio y/o un documento.
    """
    TIPO_CHOICES = [
        ("INGRESO", "Ingreso"),
        ("EGRESO", "Egreso"),
        ("AJUSTE", "Ajuste"),
    ]

    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    fecha = models.DateTimeField(default=timezone.now)

    servicio = models.ForeignKey(
        Servicio, null=True, blank=True, on_delete=models.SET_NULL, related_name="movimientos"
    )
    documento = models.ForeignKey(
        Documento, null=True, blank=True, on_delete=models.SET_NULL, related_name="movimientos"
    )

    observaciones = models.TextField(blank=True, default="")
    anulado = models.BooleanField(default=False)

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.tipo} {self.fecha:%Y-%m-%d %H:%M}"


class MovimientoDetalle(models.Model):
    """
    Detalle de movimiento: item + cantidad.
    """
    movimiento = models.ForeignKey(Movimiento, related_name="detalles", on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    cantidad = models.IntegerField(validators=[MinValueValidator(1)])

    def __str__(self):
        return f"{self.item} x {self.cantidad}"


# =========================
# PROYECTOR (PRÉSTAMOS)
# =========================
class PrestamoProyector(models.Model):
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="prestamos_proyector")
    telefono_contacto = models.CharField(max_length=50, blank=True, default="")

    fecha_retiro = models.DateTimeField(default=timezone.now)
    fecha_devolucion_estimada = models.DateField(null=True, blank=True)
    fecha_devolucion_real = models.DateTimeField(null=True, blank=True)

    incluye_prolongacion = models.BooleanField(default=False)
    incluye_pc = models.BooleanField(default=False)
    incluye_notebook = models.BooleanField(default=False)

    observaciones = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-fecha_retiro"]

    def __str__(self):
        return f"Proyector -> {self.servicio.nombre} ({self.fecha_retiro:%Y-%m-%d})"

    @property
    def devuelto(self):
        return self.fecha_devolucion_real is not None


# =========================
# PENDIENTES
# =========================
class Pendiente(models.Model):
    texto = models.CharField(max_length=255)
    completado = models.BooleanField(default=False)

    servicio = models.ForeignKey(
        Servicio,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pendientes",
    )

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["completado", "-creado"]

    def __str__(self):
        return self.texto


# =========================
# PROVEEDORES / REPARACIONES
# =========================
class Proveedor(models.Model):
    nombre = models.CharField(max_length=120)
    telefono = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    observaciones = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Reparacion(models.Model):
    ESTADOS = [
        ("RECIBIDO", "Recibido"),
        ("ENVIADO", "Enviado"),
        ("EN_REPARACION", "En reparación"),
        ("LISTO", "Listo"),
        ("RETIRADO", "Retirado"),
        ("CERRADO", "Cerrado"),
    ]

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="reparaciones")

    proveedor = models.ForeignKey(
        Proveedor,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reparaciones",
    )

    estado = models.CharField(max_length=20, choices=ESTADOS, default="RECIBIDO")
    fecha_envio = models.DateField(null=True, blank=True)
    fecha_retorno = models.DateField(null=True, blank=True)

    diagnostico = models.CharField(max_length=255, blank=True)
    seguimiento = models.TextField(blank=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"Reparación #{self.id} - {self.item}"


# =========================
# PEDIDO / PATRIMONIO
# =========================
class Pedido(models.Model):
    ESTADOS = [
        ("HECHO", "Hecho"),
        ("APROBADO", "Aprobado"),
        ("RECIBIDO", "Recibido"),
        ("ENTREGADO", "Entregado"),
        ("CANCELADO", "Cancelado"),
    ]

    numero = models.CharField(max_length=40, unique=True)  # ej: PED-2026-0001

    servicio_solicitante = models.ForeignKey(
        "Servicio",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="pedidos",
        db_index=True
    )

    numero_nota = models.CharField(max_length=50, blank=True)
    observaciones = models.TextField(blank=True)
    para_que = models.CharField(max_length=255, blank=True)

    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pedidos_creados"
    )

    estado = models.CharField(max_length=20, choices=ESTADOS, default="HECHO", db_index=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.numero} - {self.get_estado_display()}"


class PedidoDetalle(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="detalles")
    item = models.ForeignKey("Item", on_delete=models.PROTECT, db_index=True)

    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    detalle = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["pedido", "item"], name="uniq_pedido_item"),
        ]
        indexes = [
            models.Index(fields=["pedido"]),
            models.Index(fields=["item"]),
        ]

    def __str__(self):
        return f"{self.pedido.numero} - {self.item} x {self.cantidad}"


class PatrimonioUnidad(models.Model):
    """
    1 fila = 1 unidad patrimonial.
    Cuelga de PedidoDetalle (Opción A).
    """
    pedido_detalle = models.ForeignKey(
        PedidoDetalle,
        on_delete=models.CASCADE,
        related_name="patrimonios",
        db_index=True
    )

    numero_patrimonio = models.CharField(max_length=50, unique=True)
    detalle_item = models.CharField(max_length=255, blank=True)

    serial = models.CharField(max_length=80, blank=True)
    observaciones = models.TextField(blank=True)

    # Si querés registrar a qué servicio quedó asignado el patrimonio (opcional)
    servicio_asignado = models.ForeignKey(
        "Servicio",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="patrimonios_asignados",
        db_index=True
    )

    asignado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="patrimonios_creados"
    )

    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["pedido_detalle"]),
            models.Index(fields=["servicio_asignado"]),
        ]

    def __str__(self):
        return f"Patrimonio {self.numero_patrimonio}"