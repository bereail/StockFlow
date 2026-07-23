from django import forms
from django.utils import timezone

from inventario.models import Intercambio, PatrimonioUnidad, Pedido


def _patrimonio_label(obj):
    """Etiqueta rica para poder buscar por equipo o servicio, no solo por N° de patrimonio."""
    partes = [obj.numero_patrimonio, obj.nombre_pc or obj.detalle_item or ""]
    if obj.servicio_asignado_id:
        partes.append(str(obj.servicio_asignado))
    return " — ".join(p for p in partes if p)


class IntercambioForm(forms.ModelForm):
    class Meta:
        model = Intercambio
        fields = [
            "servicio_afectado",
            "servicio_beneficiario",
            "patrimonio_saliente",
            "detalle_saliente",
            "pedido_saliente",
            "motivo",
            "fecha_intercambio",
        ]
        widgets = {
            "fecha_intercambio": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "detalle_saliente": forms.TextInput(attrs={"placeholder": "Si no tiene N° de patrimonio, describilo acá"}),
            "motivo": forms.Textarea(attrs={"rows": 2, "placeholder": "Ej: urgencia en Guardia..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["patrimonio_saliente"].queryset = PatrimonioUnidad.objects.select_related(
            "servicio_asignado"
        ).order_by("numero_patrimonio")
        self.fields["patrimonio_saliente"].label_from_instance = _patrimonio_label
        self.fields["patrimonio_saliente"].required = False
        self.fields["detalle_saliente"].required = False
        self.fields["pedido_saliente"].queryset = Pedido.objects.order_by("-creado")
        self.fields["pedido_saliente"].required = False
        if not self.instance.pk and not self.initial.get("fecha_intercambio"):
            self.initial["fecha_intercambio"] = timezone.now().strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("patrimonio_saliente") and not (cleaned.get("detalle_saliente") or "").strip():
            self.add_error("detalle_saliente", "Elegí un patrimonio o describí qué se entregó.")
        if cleaned.get("servicio_afectado") and cleaned.get("servicio_afectado") == cleaned.get("servicio_beneficiario"):
            self.add_error("servicio_beneficiario", "Tiene que ser un servicio distinto al que espera la compensación.")
        return cleaned


class IntercambioResolverForm(forms.ModelForm):
    class Meta:
        model = Intercambio
        fields = ["patrimonio_entrante", "detalle_entrante", "pedido_entrante"]
        widgets = {
            "detalle_entrante": forms.TextInput(attrs={"placeholder": "Si no tiene N° de patrimonio, describilo acá"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["patrimonio_entrante"].queryset = PatrimonioUnidad.objects.select_related(
            "servicio_asignado"
        ).order_by("numero_patrimonio")
        self.fields["patrimonio_entrante"].label_from_instance = _patrimonio_label
        self.fields["patrimonio_entrante"].required = False
        self.fields["detalle_entrante"].required = False
        self.fields["pedido_entrante"].queryset = Pedido.objects.order_by("-creado")
        self.fields["pedido_entrante"].required = False

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("patrimonio_entrante") and not (cleaned.get("detalle_entrante") or "").strip():
            self.add_error("detalle_entrante", "Elegí un patrimonio o describí qué llegó.")
        return cleaned
