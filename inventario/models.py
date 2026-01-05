from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone


# =========================
# MAESTROS
# =========================

class Servicio(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Toner(models.Model):
    modelo = models.CharField(max_length=100)
    marca = models.CharField(max_length=100, blank=True, default="")
    codigo = models.CharField(max_length=100, blank=True, default="")

    stock = models.IntegerField(default=0)
    minimo = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.modelo


class Articulo(models.Model):
    nombre = models.CharField(max_length=120)
    marca = models.CharField(max_length=100, blank=True, default="")
    codigo = models.CharField(max_length=100, blank=True, default="")

    stock = models.IntegerField(default=0)
    minimo = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


# =========================
# MOVIMIENTO (CABECERA)
# =========================

class Movimiento(models.Model):
    TIPO = (
        ("INGRESO", "Ingreso a depósito"),
        ("EGRESO", "Egreso/Retiro para servicio"),
    )

    tipo = models.CharField(max_length=10, choices=TIPO)
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.PROTECT,
        related_name="movimientos",
        blank=True,
        null=True,  # null cuando es INGRESO
    )

    fecha = models.DateTimeField(default=timezone.now)

    entregado_a = models.CharField(max_length=120, blank=True)
    observaciones = models.TextField(blank=True)

    nro_pedido = models.CharField(max_length=50, blank=True)  # opcional
    nro_nota = models.CharField(max_length=50, blank=True)    # opcional

    anulado = models.BooleanField(default=False)
    anulado_motivo = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-fecha"]

    def clean(self):
        if self.tipo == "EGRESO" and not self.servicio:
            raise ValidationError("En un EGRESO debe seleccionar un servicio.")

        if self.anulado and not self.anulado_motivo:
            raise ValidationError("Si anula el movimiento, indique un motivo.")

    def __str__(self):
        s = self.servicio.nombre if self.servicio else "-"
        return f"[{self.tipo}] -> {s} {self.fecha:%Y-%m-%d %H:%M}"


# =========================
# LINEAS (DETALLE)
# =========================

class MovimientoToner(models.Model):
    movimiento = models.ForeignKey(Movimiento, on_delete=models.CASCADE, related_name="toners")
    toner = models.ForeignKey(Toner, on_delete=models.PROTECT, related_name="movimientos")
    cantidad = models.PositiveIntegerField()

    class Meta:
        ordering = ["id"]

    def clean(self):
        if self.cantidad <= 0:
            raise ValidationError("La cantidad debe ser mayor que cero.")

        # Si la cabecera está anulada, no permitimos cargar líneas
        if self.movimiento and self.movimiento.anulado:
            raise ValidationError("No se pueden agregar items a un movimiento anulado.")

        # Validar stock solo en creación y solo si es EGRESO
        if self.pk is None and self.movimiento and self.movimiento.tipo == "EGRESO":
            if self.toner.stock < self.cantidad:
                raise ValidationError(
                    f"No hay stock suficiente de {self.toner}. (Disponible: {self.toner.stock})"
                )

        # Evitar ediciones peligrosas (para no romper stock)
        if self.pk is not None:
            old = MovimientoToner.objects.get(pk=self.pk)
            if old.toner_id != self.toner_id or old.cantidad != self.cantidad or old.movimiento_id != self.movimiento_id:
                raise ValidationError(
                    "No se permite modificar toner/cantidad/movimiento en un item ya creado. "
                    "Para corregir stock, genere un movimiento inverso."
                )

    def apply_to_stock(self):
        if self.movimiento.tipo == "INGRESO":
            self.toner.stock += self.cantidad
        else:
            if self.toner.stock < self.cantidad:
                raise ValidationError("Stock insuficiente.")
            self.toner.stock -= self.cantidad
        self.toner.save(update_fields=["stock"])

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.full_clean()
        with transaction.atomic():
            super().save(*args, **kwargs)
            if is_new:
                self.apply_to_stock()

    def __str__(self):
        return f"{self.cantidad} x {self.toner}"


class MovimientoArticulo(models.Model):
    movimiento = models.ForeignKey(Movimiento, on_delete=models.CASCADE, related_name="articulos")
    articulo = models.ForeignKey(Articulo, on_delete=models.PROTECT, related_name="movimientos")
    cantidad = models.PositiveIntegerField()

    class Meta:
        ordering = ["id"]

    def clean(self):
        if self.cantidad <= 0:
            raise ValidationError("La cantidad debe ser mayor que cero.")

        if self.movimiento and self.movimiento.anulado:
            raise ValidationError("No se pueden agregar items a un movimiento anulado.")

        if self.pk is None and self.movimiento and self.movimiento.tipo == "EGRESO":
            if self.articulo.stock < self.cantidad:
                raise ValidationError(
                    f"No hay stock suficiente de {self.articulo}. (Disponible: {self.articulo.stock})"
                )

        if self.pk is not None:
            old = MovimientoArticulo.objects.get(pk=self.pk)
            if old.articulo_id != self.articulo_id or old.cantidad != self.cantidad or old.movimiento_id != self.movimiento_id:
                raise ValidationError(
                    "No se permite modificar artículo/cantidad/movimiento en un item ya creado. "
                    "Para corregir stock, genere un movimiento inverso."
                )

    def apply_to_stock(self):
        if self.movimiento.tipo == "INGRESO":
            self.articulo.stock += self.cantidad
        else:
            if self.articulo.stock < self.cantidad:
                raise ValidationError("Stock insuficiente.")
            self.articulo.stock -= self.cantidad
        self.articulo.save(update_fields=["stock"])

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.full_clean()
        with transaction.atomic():
            super().save(*args, **kwargs)
            if is_new:
                self.apply_to_stock()

    def __str__(self):
        return f"{self.cantidad} x {self.articulo}"
