from django import forms
from ..models import ActivoPC, Impresora


class ActivoPCForm(forms.ModelForm):
    class Meta:
        model = ActivoPC
        fields = [
            "nombre_pc",
            "activo",
            "servicio",
            "ip",
            "switch",
            "usuario",
            "impresora",
            "patrimonio",
            "serie",
            "caracteristicas",
            "observaciones",
        ]
        widgets = {
            "nombre_pc": forms.TextInput(attrs={"placeholder": "Ej: PC Guardia 1 / PC Administración"}),
            "ip": forms.TextInput(attrs={"placeholder": "192.168.1.50 (opcional)"}),
            "switch": forms.TextInput(attrs={"placeholder": "Ej: SW-PB-03 / Puerto 12 (opcional)"}),
            "usuario": forms.TextInput(attrs={"placeholder": "Nombre de quien la usa (opcional)"}),
            "patrimonio": forms.TextInput(attrs={"placeholder": "N° Patrimonio (opcional)"}),
            "serie": forms.TextInput(attrs={"placeholder": "N° Serie (opcional)"}),
            "caracteristicas": forms.Textarea(attrs={"rows": 2, "placeholder": "Características (opcional)"}),
            "observaciones": forms.Textarea(attrs={"rows": 2, "placeholder": "Observaciones (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ["ip", "switch", "usuario", "impresora", "patrimonio", "serie", "caracteristicas", "observaciones", "servicio"]:
            self.fields[campo].required = False

        self.fields["impresora"].queryset = Impresora.objects.filter(activo=True).order_by("marca", "modelo")
        self.fields["impresora"].empty_label = "-- Sin impresora asociada --"
