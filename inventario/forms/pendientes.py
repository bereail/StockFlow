from django import forms
from inventario.models import Pendiente

class PendienteForm(forms.ModelForm):
    class Meta:
        model = Pendiente
        fields = ["texto", "servicio"]
        widgets = {
            "texto": forms.TextInput(attrs={
                "placeholder": "Anotar pendiente…",
                "autofocus": True,
            }),
        }