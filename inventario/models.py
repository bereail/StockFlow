
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db.models import Q, F
from django.conf import settings

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

    es_patrimonial = models.BooleanField(
        default=False,
        verbose_name="Es patrimonial",
        help_text="Cada unidad cargada en un pedido va a pedir su propio N° de patrimonio.",
    )

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
    Impresoras del sistema (objeto físico).
    NO tiene servicio directo: el servicio se maneja con AsignacionImpresora (historial).
    """

    TIPO_CONEXION = (
        ("IP", "Red"),
        ("USB", "USB"),
    )

    articulo = models.ForeignKey(
        "Articulo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="impresoras",
        verbose_name="Artículo de catálogo",
        help_text="Artículo patrimonial del que sale esta unidad (ej: 'Impresora Brother HL 1212').",
    )

    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)

    # Si esto representa "Laser / Inkjet / Multifunción", conviene choices.
    tipo = models.CharField(max_length=100)

    patrimonio = models.CharField(max_length=100, blank=True)

    activo = models.BooleanField(default=True)
    estado = models.CharField(max_length=50, default="ACTIVA")

    conexion = models.CharField(max_length=10, choices=TIPO_CONEXION)
    ip = models.GenericIPAddressField(protocol="IPv4", blank=True, null=True)

    toner = models.ForeignKey(
        "Toner",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="impresoras",
    )

    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["marca", "modelo"]

    def __str__(self):
        return f"{self.marca} {self.modelo}"

    def clean(self):
        if self.conexion == "IP" and not self.ip:
            raise ValidationError({"ip": "Si la conexión es por red (IP), debés cargar la IP."})

    @property
    def asignacion_activa(self):
        # Requiere related_name="asignaciones" en AsignacionImpresora
        return self.asignaciones.filter(fecha_hasta__isnull=True).order_by("-fecha_desde").first()

    @property
    def servicio_actual(self):
        a = self.asignacion_activa
        return a.servicio if a else None

    @property
    def ubicacion_actual(self):
        a = self.asignacion_activa
        return a.ubicacion if a else ""

    @property
    def responsable_actual(self):
        a = self.asignacion_activa
        return a.responsable if a else ""

class AsignacionImpresora(models.Model):
    """
    Historial de asignación de una impresora a un servicio.
    Solo 1 asignación puede estar activa (fecha_hasta NULL) por impresora.
    """

    impresora = models.ForeignKey(
        Impresora,
        on_delete=models.PROTECT,
        related_name="asignaciones",
    )

    servicio = models.ForeignKey(
        "Servicio",
        on_delete=models.PROTECT,
        related_name="impresoras_asignadas",
    )

    fecha_desde = models.DateField(default=timezone.now)
    fecha_hasta = models.DateField(null=True, blank=True)

    ubicacion = models.CharField(max_length=100, blank=True, default="")
    responsable = models.CharField(max_length=120, blank=True, default="")
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["-fecha_desde"]
        constraints = [
            models.UniqueConstraint(
                fields=["impresora"],
                condition=Q(fecha_hasta__isnull=True),
                name="uniq_asignacion_activa_por_impresora",
            )
        ]

    def __str__(self):
        desde = self.fecha_desde.isoformat() if self.fecha_desde else ""
        hasta = self.fecha_hasta.isoformat() if self.fecha_hasta else "Actual"
        return f"{self.impresora} -> {self.servicio} ({desde} a {hasta})"

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
    """
    TIPO_CHOICES = [
        ("TONER", "Toner"),
        ("ARTICULO", "Artículo"),
        ("ACTIVO_PC", "Activo PC"),
        ("IMPRESORA", "Impresora"),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)

    toner = models.ForeignKey(Toner, null=True, blank=True, on_delete=models.PROTECT)
    articulo = models.ForeignKey(Articulo, null=True, blank=True, on_delete=models.PROTECT)
    activo_pc = models.ForeignKey(ActivoPC, null=True, blank=True, on_delete=models.PROTECT)
    impresora = models.ForeignKey(Impresora, null=True, blank=True, on_delete=models.PROTECT)
    es_combo = models.BooleanField(default=False)
    
    prestable = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    (Q(toner__isnull=False) & Q(articulo__isnull=True) & Q(activo_pc__isnull=True) & Q(impresora__isnull=True)) |
                    (Q(toner__isnull=True) & Q(articulo__isnull=False) & Q(activo_pc__isnull=True) & Q(impresora__isnull=True)) |
                    (Q(toner__isnull=True) & Q(articulo__isnull=True) & Q(activo_pc__isnull=False) & Q(impresora__isnull=True)) |
                    (Q(toner__isnull=True) & Q(articulo__isnull=True) & Q(activo_pc__isnull=True) & Q(impresora__isnull=False))
                ),
                name="chk_item_exactamente_un_fk",
            ),
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

class ItemComponente(models.Model):
    item_padre = models.ForeignKey("Item", on_delete=models.CASCADE, related_name="componentes")
    item_hijo = models.ForeignKey("Item", on_delete=models.PROTECT, related_name="usado_en_combos")
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)], default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["item_padre", "item_hijo"], name="uniq_combo_componente"),
            models.CheckConstraint(check=~Q(item_padre=F("item_hijo")), name="chk_no_auto_referencia")
        ]

    def clean(self):
        if not self.item_padre.es_combo:
            raise ValidationError("El item padre debe estar marcado como combo.")
        if self.item_hijo.es_combo:
            raise ValidationError("Un combo no puede incluir otro combo (por ahora).")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item_padre} incluye {self.item_hijo} x{self.cantidad}"
    
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
# (PRÉSTAMOS)
# =========================
class Prestamo(models.Model):
    servicio = models.ForeignKey(
        "Servicio",
        on_delete=models.PROTECT,
        related_name="prestamos",
        null=True,
        blank=True,
    )
    telefono_contacto = models.CharField(max_length=50, blank=True, default="")
    entregado_a = models.CharField(max_length=120, blank=True, default="")

    fecha_retiro = models.DateTimeField(default=timezone.now)
    fecha_devolucion_estimada = models.DateField(null=True, blank=True)
    fecha_devolucion_real = models.DateTimeField(null=True, blank=True)

    observaciones = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-fecha_retiro"]

    def __str__(self):
        # Evita "Prestamo object (1)"
        servicio = getattr(self.servicio, "nombre", None) or "Sin servicio"
        return f" {servicio}"

    @property
    def devuelto(self):
        return self.fecha_devolucion_real is not None

    @property
    def items_label(self):
        partes = [
            f"{d.item}" + (f" x{d.cantidad}" if d.cantidad > 1 else "") + (f" — {d.detalle}" if d.detalle else "")
            for d in self.detalles.all()
        ]
        return ", ".join(partes) if partes else "—"

    @property
    def dias_restantes(self):
        if self.fecha_devolucion_estimada and not self.devuelto:
            from django.utils import timezone
            return (self.fecha_devolucion_estimada - timezone.localdate()).days
        return None

class PrestamoDetalle(models.Model):
    prestamo = models.ForeignKey(
        Prestamo,
        on_delete=models.CASCADE,
        related_name="detalles",
    )

    item = models.ForeignKey(
        "Item",
        on_delete=models.PROTECT,
        related_name="prestamos_detalle",
    )

    cantidad = models.PositiveIntegerField(default=1)
    detalle = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        extra = f" ({self.detalle})" if self.detalle else ""
        return f"{self.item} x{self.cantidad}{extra}"
    
# =========================
# PENDIENTES
# =========================
class Pendiente(models.Model):
    ESTADOS = [
        ("PENDIENTE",   "Pendiente"),
        ("EN_PROGRESO", "En progreso"),
        ("COMPLETADO",  "Completado"),
        ("CANCELADO",   "Cancelado"),
    ]

    texto = models.CharField(max_length=255)
    estado = models.CharField(max_length=20, choices=ESTADOS, default="PENDIENTE", db_index=True)
    fecha_limite = models.DateField(null=True, blank=True)

    servicio = models.ForeignKey(
        Servicio,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pendientes",
    )

    pedido = models.ForeignKey(
        "Pedido",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pendientes",
        verbose_name="Pedido vinculado",
    )

    creado = models.DateTimeField(auto_now_add=True)
    observacion = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["estado", "-creado"]

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

    servicio = models.ForeignKey(
        Servicio,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
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

    numero = models.CharField(max_length=40, unique=True)

    servicio_solicitante = models.ForeignKey(
        "Servicio",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pedidos",
        db_index=True,
    )

    numero_nota = models.CharField(max_length=50, blank=True)
    observaciones = models.TextField(blank=True)
    para_que = models.CharField(max_length=255, blank=True)

    proveedor = models.ForeignKey(
        "Proveedor",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="pedidos",
        verbose_name="Proveedor",
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="HECHO",
        db_index=True,
    )

    fecha_aprobado  = models.DateField(null=True, blank=True, verbose_name="Fecha aprobación")
    fecha_recibido  = models.DateField(null=True, blank=True, verbose_name="Fecha recepción")
    fecha_entregado = models.DateField(null=True, blank=True, verbose_name="Fecha entrega")

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
    1 fila = 1 unidad patrimonial de un artículo de catálogo.
    Puede colgar de un PedidoDetalle (unidad recibida por ese pedido) o
    existir de forma independiente (unidad registrada directamente contra
    el artículo, sin pasar por un pedido).
    """
    articulo = models.ForeignKey(
        "Articulo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="patrimonios",
        db_index=True,
    )

    pedido_detalle = models.ForeignKey(
        PedidoDetalle,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="patrimonios",
        db_index=True
    )

    numero_patrimonio = models.CharField(max_length=50, unique=True)
    detalle_item = models.CharField(max_length=255, blank=True)

    nombre_pc       = models.CharField(max_length=120, blank=True, verbose_name="Nombre del equipo")
    ip              = models.CharField(max_length=45,  blank=True, verbose_name="Dirección IP")
    usuario_asignado = models.CharField(max_length=120, blank=True, verbose_name="Usuario asignado")

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


# =========================
# NOTA
# =========================
class Nota(models.Model):
    ESTADOS = [
        ("BORRADOR", "Borrador"),
        ("ENVIADA", "Enviada"),
        ("APROBADA", "Aprobada"),
        ("CERRADA", "Cerrada"),
        ("CANCELADA", "Cancelada"),
    ]

    numero = models.CharField(max_length=50, blank=True, default="")

    servicio_solicitante = models.ForeignKey(
        "Servicio",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notas",
        db_index=True,
    )

    fecha = models.DateField(default=timezone.now)
    detalle = models.TextField(blank=True, default="")
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="BORRADOR",
        db_index=True
    )

    # ✅ NUEVO CAMPO
    fecha_cierre = models.DateTimeField(null=True, blank=True)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha", "-creado"]
        indexes = [
            models.Index(fields=["estado"]),
            models.Index(fields=["fecha"]),
        ]

    def save(self, *args, **kwargs):
        """
        Lógica automática:
        - Si pasa a CERRADA → setea fecha_cierre
        - Si deja de estar cerrada → limpia fecha_cierre
        """

        if self.estado == "CERRADA" and self.fecha_cierre is None:
            self.fecha_cierre = timezone.now()

        if self.estado != "CERRADA" and self.fecha_cierre is not None:
            self.fecha_cierre = None

        super().save(*args, **kwargs)

    def __str__(self):
        num = self.numero.strip() or "Sin número"
        serv = getattr(self.servicio_solicitante, "nombre", None) or "Sin servicio"
        return f"Nota {num} - {serv} ({self.fecha:%Y-%m-%d})"

class NotaDetalle(models.Model):
    nota = models.ForeignKey(Nota, on_delete=models.CASCADE, related_name="detalles")
    item = models.ForeignKey("Item", on_delete=models.PROTECT, db_index=True)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)], default=1)
    detalle = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["nota", "item"], name="uniq_nota_item"),
        ]

    def __str__(self):
        extra = f" ({self.detalle})" if self.detalle else ""
        return f"{self.item} x {self.cantidad}{extra}"