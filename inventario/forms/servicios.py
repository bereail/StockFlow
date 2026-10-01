from django import forms
from ..models import Servicio


class ServicioForm(forms.ModelForm):
    class Meta:
        model = Servicio
        fields = ["nombre"]
        widgets = {
            "nombre": forms.TextInput(
                attrs={"placeholder": "Ej: Terapia Intensiva"}
            ),
        }
