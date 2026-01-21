from django import forms
from ..models import ActivoPC


class ActivoPCForm(forms.ModelForm):
    class Meta:
        model = ActivoPC
        fields = [
            "nombre_pc",
            "activo",
            "ip",
            "patrimonio",
            "serie",
            "caracteristicas",
            "observaciones",
            "servicio",
        ]
        widgets = {
            "nombre_pc": forms.TextInput(attrs={"placeholder": "Ej: PC Guardia 1 / PC Administración"}),
            "ip": forms.TextInput(attrs={"placeholder": "192.168.1.50 (opcional)"}),
            "patrimonio": forms.TextInput(attrs={"placeholder": "N° Patrimonio (opcional)"}),
            "serie": forms.TextInput(attrs={"placeholder": "N° Serie (opcional)"}),
            "caracteristicas": forms.Textarea(attrs={"rows": 2, "placeholder": "Características (opcional)"}),
            "observaciones": forms.Textarea(attrs={"rows": 2, "placeholder": "Observaciones (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ip"].required = False
        self.fields["patrimonio"].required = False
        self.fields["serie"].required = False
        self.fields["caracteristicas"].required = False
        self.fields["observaciones"].required = False
        self.fields["servicio"].required = False
