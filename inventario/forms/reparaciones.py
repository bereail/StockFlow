from django import forms
from inventario.models import Reparacion

class ReparacionForm(forms.ModelForm):
    class Meta:
        model = Reparacion
        fields = [
            "item",
            "servicio",
            "proveedor",
            "estado",
            "fecha_envio",
            "fecha_retorno",
            "diagnostico",
            "seguimiento",
        ]
        widgets = {
            "fecha_envio": forms.DateInput(attrs={"type": "date"}),
            "fecha_retorno": forms.DateInput(attrs={"type": "date"}),
            "diagnostico": forms.TextInput(attrs={"placeholder": "Ej: No imprime / atasca / error SC..."}),
            "seguimiento": forms.Textarea(attrs={"rows": 3, "placeholder": "Notas de seguimiento..."}),
        }