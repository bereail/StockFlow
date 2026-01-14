from django.db import models
from django.utils import timezone


# =========================
# CATÁLOGOS
# =========================

class Servicio(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return self.nombre


class Toner(models.Model):
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)
    marca = models.CharField(max_length=100, blank=True)
    modelo_impresora = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.nombre} ({self.marca})"


class Articulo(models.Model):
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    marca = models.CharField(max_length=100, blank=True)
    caracteristicas = models.TextField(blank=True)
    observaciones = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class ActivoPC(models.Model):
    nombre_pc = models.CharField(max_length=100)
    ip = models.GenericIPAddressField(protocol="IPv4", blank=True, null=True)
    patrimonio = models.CharField(max_length=100, blank=True)
    serie = models.CharField(max_length=100, blank=True)
    caracteristicas = models.TextField(blank=True)
    observaciones = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    servicio = models.ForeignKey(
        Servicio, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return self.nombre_pc


class Impresora(models.Model):
    TIPO_CONEXION = (
        ("IP", "Red"),
        ("USB", "USB"),
    )

    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    tipo = models.CharField(max_length=100)

    patrimonio = models.CharField(max_length=100, blank=True)

    activo = models.BooleanField(default=True)
    estado = models.CharField(max_length=50, default="ACTIVA")

    servicio = models.ForeignKey("Servicio", on_delete=models.SET_NULL, null=True, blank=True)
    conexion = models.CharField(max_length=10, choices=TIPO_CONEXION)
    ip = models.GenericIPAddressField(protocol="IPv4", blank=True, null=True)

    toner = models.ForeignKey("Toner", on_delete=models.SET_NULL, null=True, blank=True)
    observaciones = models.TextField(blank=True)

    def __str__(self):
        return f"{self.marca} {self.modelo}"
        
        

# =========================
# DOCUMENTOS ADMINISTRATIVOS
# =========================

class Documento(models.Model):
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
        unique_together = ("tipo", "numero")

    def __str__(self):
        return f"{self.tipo} Nº {self.numero}"


# =========================
# MOVIMIENTOS DE INVENTARIO
# =========================

class Item(models.Model):
    TIPO_CHOICES = [
        ("TONER", "Toner"),
        ("ARTICULO", "Artículo"),
        ("ACTIVO_PC", "Activo PC"),
        ("IMPRESORA", "Impresora"),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)

    toner = models.ForeignKey("Toner", null=True, blank=True, on_delete=models.CASCADE)
    articulo = models.ForeignKey("Articulo", null=True, blank=True, on_delete=models.CASCADE)
    activo_pc = models.ForeignKey("ActivoPC", null=True, blank=True, on_delete=models.CASCADE)
    impresora = models.ForeignKey("Impresora", null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        if self.toner: return f"TONER: {self.toner}"
        if self.articulo: return f"ARTICULO: {self.articulo}"
        if self.activo_pc: return f"ACTIVO_PC: {self.activo_pc}"
        if self.impresora: return f"IMPRESORA: {self.impresora}"
        return f"Item #{self.pk}"

class Movimiento(models.Model):
    TIPO_CHOICES = [
        ("INGRESO", "Ingreso"),
        ("EGRESO", "Egreso"),
        ("AJUSTE", "Ajuste"),
    ]

    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    fecha = models.DateTimeField(default=timezone.now)
    servicio = models.ForeignKey("Servicio", null=True, blank=True, on_delete=models.SET_NULL)
    documento = models.ForeignKey("Documento", null=True, blank=True, on_delete=models.SET_NULL)
    observaciones = models.TextField(blank=True, default="")
    anulado = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.tipo} {self.fecha:%Y-%m-%d %H:%M}"

class MovimientoDetalle(models.Model):
    movimiento = models.ForeignKey(Movimiento, related_name="detalles", on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    cantidad = models.IntegerField()

    def __str__(self):
        return f"{self.item} x {self.cantidad}"

# PROYECTOR #
class PrestamoProyector(models.Model):
    servicio = models.ForeignKey("Servicio", on_delete=models.PROTECT)
    telefono_contacto = models.CharField(max_length=50, blank=True, default="")

    fecha_retiro = models.DateTimeField(default=timezone.now)
    fecha_devolucion_estimada = models.DateField(null=True, blank=True)
    fecha_devolucion_real = models.DateTimeField(null=True, blank=True)

    # items incluidos (checklist simple)
    incluye_prolongacion = models.BooleanField(default=False)
    incluye_pc = models.BooleanField(default=False)
    incluye_notebook = models.BooleanField(default=False)

    observaciones = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Proyector -> {self.servicio.nombre} ({self.fecha_retiro:%Y-%m-%d})"

    @property
    def devuelto(self):
        return self.fecha_devolucion_real is not None