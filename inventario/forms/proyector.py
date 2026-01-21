from django import forms
from inventario.models import PrestamoProyector

class PrestamoProyectorForm(forms.ModelForm):
    class Meta:
        model = PrestamoProyector
        fields = [
            "servicio",
            "telefono_contacto",
            "fecha_retiro",
            "fecha_devolucion_estimada",
            "incluye_prolongacion",
            "incluye_pc",
            "incluye_notebook",
            "observaciones",
        ]
        widgets = {
            "fecha_retiro": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "fecha_devolucion_estimada": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
            "telefono_contacto": forms.TextInput(attrs={"placeholder": "Ej: 381-xxxxxxx"}),
        }