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
    estado = models.CharField(max_length=50, default="ACTIVA")
    servicio = models.ForeignKey(
        Servicio, on_delete=models.SET_NULL, null=True, blank=True
    )
    conexion = models.CharField(max_length=10, choices=TIPO_CONEXION)
    ip = models.GenericIPAddressField(protocol="IPv4", blank=True, null=True)
    toner = models.ForeignKey(
        Toner, on_delete=models.SET_NULL, null=True, blank=True
    )
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
    TIPO_ITEM = (
        ("TONER", "Toner"),
        ("ARTICULO", "Artículo"),
        ("ACTIVO_PC", "PC"),
    )

    tipo = models.CharField(max_length=20, choices=TIPO_ITEM)
    toner = models.ForeignKey(Toner, null=True, blank=True, on_delete=models.CASCADE)
    articulo = models.ForeignKey(Articulo, null=True, blank=True, on_delete=models.CASCADE)
    activo_pc = models.ForeignKey(ActivoPC, null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        if self.toner:
            return f"Toner: {self.toner}"
        if self.articulo:
            return f"Artículo: {self.articulo}"
        if self.activo_pc:
            return f"PC: {self.activo_pc}"
        return "Item"


class Movimiento(models.Model):
    TIPO_MOVIMIENTO = (
        ("INGRESO", "Ingreso"),
        ("EGRESO", "Egreso"),
        ("AJUSTE", "Ajuste"),
    )

    fecha = models.DateTimeField(default=timezone.now)
    tipo = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO)
    servicio = models.ForeignKey(
        Servicio, on_delete=models.SET_NULL, null=True, blank=True
    )
    documento = models.ForeignKey(
        Documento, on_delete=models.SET_NULL, null=True, blank=True
    )
    observaciones = models.TextField(blank=True)

    def __str__(self):
        return f"{self.tipo} - {self.fecha.strftime('%d/%m/%Y')}"


class MovimientoDetalle(models.Model):
    movimiento = models.ForeignKey(
        Movimiento, related_name="detalles", on_delete=models.CASCADE
    )
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    cantidad = models.IntegerField()

    def __str__(self):
        return f"{self.item} x {self.cantidad}"
