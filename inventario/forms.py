from django import forms
from .models import Toner, Movimiento, Servicio

class TonerForm(forms.ModelForm):
    class Meta:
        model = Toner
        fields = ["marca", "modelo", "codigo", "stock", "minimo"]
        widgets = {
            "marca": forms.TextInput(attrs={"placeholder": "HP"}),
            "modelo": forms.TextInput(attrs={"placeholder": "12A / Q2612A"}),
            "codigo": forms.TextInput(attrs={"placeholder": "Código interno (opcional)"}),
        }

class MovimientoForm(forms.ModelForm):
    class Meta:
        model = Movimiento
        fields = ["toner", "tipo", "cantidad", "servicio", "entregado_a", "observaciones"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # servicios opcional por defecto (tu clean ya valida si EGRESO)
        self.fields["servicio"].required = False
