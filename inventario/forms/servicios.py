from django import forms
from ..models import Servicio


class ServicioForm(forms.ModelForm):
    class Meta:
        model = Servicio
        fields = ["nombre", "descripcion"]
        widgets = {
            "nombre": forms.TextInput(
                attrs={"placeholder": "Ej: Terapia Intensiva"}
            ),
            "descripcion": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Opcional"}
            ),
        }
