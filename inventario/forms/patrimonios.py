from django import forms
from ..models import Articulo, PatrimonioUnidad


class PatrimonioStandaloneForm(forms.ModelForm):
    """
    Registra una unidad patrimonial directamente contra un artículo del
    catálogo, sin necesidad de pasar por un pedido. Queda disponible para
    vincularla después a un pedido o a una entrega rápida.
    """
    class Meta:
        model = PatrimonioUnidad
        fields = [
            "articulo",
            "numero_patrimonio",
            "detalle_item",
            "nombre_pc",
            "ip",
            "usuario_asignado",
            "serial",
            "observaciones",
            "servicio_asignado",
        ]
        widgets = {
            "detalle_item":     forms.TextInput(attrs={"placeholder": "Ej: Monitor Samsung 24' (opcional)"}),
            "nombre_pc":        forms.TextInput(attrs={"placeholder": "Nombre / identificador (opcional)"}),
            "ip":               forms.TextInput(attrs={"placeholder": "Ej: 192.168.1.42 (opcional)"}),
            "usuario_asignado": forms.TextInput(attrs={"placeholder": "Nombre del usuario (opcional)"}),
            "observaciones":    forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        self.fields["articulo"].queryset = Articulo.objects.filter(es_patrimonial=True).order_by("nombre")
        self.fields["articulo"].empty_label = None

        for f in ["detalle_item", "nombre_pc", "ip", "usuario_asignado", "serial", "observaciones", "servicio_asignado"]:
            self.fields[f].required = False

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.pedido_detalle = None
        obj.asignado_por = self.user
        if commit:
            obj.save()
        return obj
