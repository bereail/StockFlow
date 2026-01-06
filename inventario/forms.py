from django import forms
from .models import (
    Toner,
    Articulo,
    Servicio,
    Movimiento,
    MovimientoToner,
    MovimientoArticulo,
)

# =========================
# TONER
# =========================
class TonerForm(forms.ModelForm):
    class Meta:
        model = Toner
        fields = ["marca", "modelo", "stock", "minimo"]
        widgets = {
            "marca": forms.TextInput(attrs={"placeholder": "HP"}),
            "modelo": forms.TextInput(attrs={"placeholder": "12A / Q2612A"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["marca"].required = False
        self.fields["stock"].required = False
        self.fields["minimo"].required = False


# =========================
# ARTICULO
# =========================
class ArticuloForm(forms.ModelForm):
    class Meta:
        model = Articulo
        fields = [
            "nombre",
            "marca",
            "descripcion",
            "unidad",
            "categoria",
            "ubicacion",
            "stock",
            "minimo",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Cable USB / Mouse / Resma A4"}),
            "marca": forms.TextInput(attrs={"placeholder": "Genérica / HP / Logitech (opcional)"}),
            "descripcion": forms.Textarea(attrs={"rows": 2, "placeholder": "Descripción (opcional)"}),
            "unidad": forms.TextInput(attrs={"placeholder": "u / pack / caja (opcional)"}),
            "categoria": forms.TextInput(attrs={"placeholder": "Ej: Oficina / PC / Limpieza (opcional)"}),
            "ubicacion": forms.TextInput(attrs={"placeholder": "Ej: Depósito / Estante 3 (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo nombre obligatorio
        self.fields["marca"].required = False
        self.fields["descripcion"].required = False
        self.fields["unidad"].required = False
        self.fields["categoria"].required = False
        self.fields["ubicacion"].required = False
        self.fields["stock"].required = False
        self.fields["minimo"].required = False


# =========================
# MOVIMIENTO (CABECERA)
# =========================
class MovimientoForm(forms.ModelForm):
    class Meta:
        model = Movimiento
        fields = [
            "tipo",
            "servicio",
            "fecha",
            "entregado_a",
            "observaciones",
            "nro_pedido",
            "nro_nota",
            "nro_orden_provision",
        ]
        widgets = {
            "fecha": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "entregado_a": forms.TextInput(attrs={"placeholder": "Nombre / sector (opcional)"}),
            "nro_pedido": forms.TextInput(attrs={"placeholder": "Pedido (opcional)"}),
            "nro_nota": forms.TextInput(attrs={"placeholder": "N° Nota (opcional)"}),
            "nro_orden_provision": forms.TextInput(attrs={"placeholder": "Orden de provisión (opcional)"}),
            "observaciones": forms.Textarea(attrs={"rows": 2, "placeholder": "Observaciones (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # En INGRESO el servicio debe quedar vacío
        self.fields["servicio"].required = False
        self.fields["fecha"].required = False
        self.fields["entregado_a"].required = False
        self.fields["observaciones"].required = False
        self.fields["nro_pedido"].required = False
        self.fields["nro_nota"].required = False
        self.fields["nro_orden_provision"].required = False

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        servicio = cleaned.get("servicio")

        if tipo == "EGRESO" and not servicio:
            self.add_error("servicio", "En un EGRESO debe seleccionar un servicio.")

        # Si es INGRESO, limpiamos servicio por las dudas
        if tipo == "INGRESO":
            cleaned["servicio"] = None

        return cleaned


# =========================
# LINEAS (ITEMS)
# =========================
class MovimientoTonerForm(forms.ModelForm):
    class Meta:
        model = MovimientoToner
        fields = ["toner", "cantidad"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # para que no moleste al crear filas vacías
        self.fields["cantidad"].required = False


class MovimientoArticuloForm(forms.ModelForm):
    class Meta:
        model = MovimientoArticulo
        fields = ["articulo", "cantidad"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # para que no moleste al crear filas vacías
        self.fields["cantidad"].required = False
