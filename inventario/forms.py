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
        fields = ["marca", "modelo", "codigo", "stock", "minimo"]
        widgets = {
            "marca": forms.TextInput(attrs={"placeholder": "HP"}),
            "modelo": forms.TextInput(attrs={"placeholder": "12A / Q2612A"}),
            "codigo": forms.TextInput(attrs={"placeholder": "Código interno (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["minimo"].required = False
        self.fields["stock"].required = False
        self.fields["marca"].required = False
        self.fields["codigo"].required = False


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
        ]
        widgets = {
            "fecha": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "entregado_a": forms.TextInput(attrs={"placeholder": "Nombre / sector (opcional)"}),
            "nro_pedido": forms.TextInput(attrs={"placeholder": "OP / Pedido (opcional)"}),
            "nro_nota": forms.TextInput(attrs={"placeholder": "N° Nota (opcional)"}),
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
        self.fields["cantidad"].required = False  # para que no moleste al crear filas vacías


class MovimientoArticuloForm(forms.ModelForm):
    class Meta:
        model = MovimientoArticulo
        fields = ["articulo", "cantidad"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cantidad"].required = False
