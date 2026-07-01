from django import forms
from inventario.models import Pendiente


class PendienteForm(forms.ModelForm):
    class Meta:
        model = Pendiente
        fields = ["texto", "fecha_limite", "servicio", "observacion"]
        widgets = {
            "texto": forms.TextInput(attrs={
                "placeholder": "Describí la tarea pendiente…",
                "autofocus": True,
            }),
            "fecha_limite": forms.DateInput(attrs={"type": "date"}),
            "observacion": forms.Textarea(attrs={"rows": 2, "placeholder": "Observaciones (opcional)"}),
        }
