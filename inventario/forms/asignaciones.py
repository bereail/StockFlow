from django import forms
from ..models import AsignacionImpresora


class AsignacionImpresoraForm(forms.ModelForm):
    class Meta:
        model = AsignacionImpresora
        fields = ["servicio", "fecha_desde", "ubicacion", "responsable", "observaciones"]
        widgets = {
            "fecha_desde": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
        }
