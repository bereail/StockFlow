from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

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



class Movimiento(models.Model):
    TIPO = (
        ("INGRESO", "Ingreso a depósito"),
        ("EGRESO", "Egreso/Retiro para servicio"),
    )
    toner = models.ForeignKey(Toner, on_delete=models.PROTECT, related_name="movimientos")
    servicio = models.ForeignKey(
        Servicio, on_delete=models.PROTECT, related_name="movimientos",
        blank=True, null=True
    )  # null cuando es INGRESO
    tipo = models.CharField(max_length=10, choices=TIPO)
    cantidad = models.PositiveIntegerField()
    fecha = models.DateTimeField(default=timezone.now)
    entregado_a = models.CharField(max_length=120, blank=True)
    observaciones = models.TextField(blank=True)
    anulado = models.BooleanField(default=False)
    anulado_motivo = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-fecha"]

    def clean(self):
        if self.tipo == "EGRESO" and not self.servicio:
            raise ValidationError("En un EGRESO debe seleccionar un servicio.")
        if self.cantidad <= 0:
            raise ValidationError("La cantidad debe ser mayor que cero.")

        if self.pk is None and self.tipo == "EGRESO":
            if self.toner.stock < self.cantidad:
                raise ValidationError(
                    f"No hay stock suficiente de {self.toner}. (Disponible: {self.toner.stock})"
                )

    def apply_to_stock(self):
        if self.tipo == "INGRESO":
            self.toner.stock += self.cantidad
        else:
            if self.toner.stock < self.cantidad:
                raise ValidationError("Stock insuficiente.")
            self.toner.stock -= self.cantidad
        self.toner.save(update_fields=["stock"])

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.full_clean()
        super().save(*args, **kwargs)
        if is_new:
            self.apply_to_stock()

    def __str__(self):
        s = self.servicio.nombre if self.servicio else "-"
        return f"[{self.tipo}] {self.cantidad} x {self.toner} -> {s} {self.fecha:%Y-%m-%d %H:%M}"
