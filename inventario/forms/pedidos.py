from ..models import Pedido, PedidoDetalle, PatrimonioUnidad

from django.utils import timezone
from django.forms import inlineformset_factory
from django import forms

class PedidoForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = [
            "numero",
            "servicio_solicitante",
            "numero_nota",
            "para_que",
            "observaciones",
            "estado",
        ]
        widgets = {
            "observaciones": forms.Textarea(attrs={"rows": 2}),
            "para_que": forms.TextInput(attrs={"placeholder": "Motivo / para qué"}),
            "numero": forms.TextInput(attrs={"placeholder": "Ej: PED-2026-0001"}),
            "numero_nota": forms.TextInput(attrs={"placeholder": "Opcional"}),
        }

    def clean(self):
        cleaned = super().clean()
        estado = cleaned.get("estado")
        # Regla: ENTREGADO requiere RECIBIDO antes (simple)
        # Si querés más estricto, hacelo en view comparando estado anterior.
        if estado == "ENTREGADO":
            # Si el pedido es nuevo, no puede nacer entregado
            if self.instance.pk is None:
                raise forms.ValidationError("No podés crear un pedido directamente como ENTREGADO.")
        return cleaned
    
PedidoDetalleFormSet = inlineformset_factory(
    Pedido,
    PedidoDetalle,
    fields=["item", "cantidad", "detalle"],
    extra=1,
    can_delete=True,
    widgets={
        "detalle": forms.TextInput(attrs={"placeholder": "Detalle opcional (marca/modelo/etc.)"})
    }
)

class PatrimonioUnidadForm(forms.ModelForm):
    class Meta:
        model = PatrimonioUnidad
        fields = [
            "numero_patrimonio",
            "detalle_item",
            "serial",
            "observaciones",
            "servicio_asignado",
        ]
        widgets = {
            "detalle_item": forms.TextInput(attrs={"placeholder": "Detalle libre (ej: PC Dell...)",}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, pedido_detalle=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pedido_detalle = pedido_detalle
        self.user = user

    def clean(self):
        cleaned = super().clean()
        if not self.pedido_detalle:
            return cleaned

        # límite por cantidad pedida
        ya_cargados = self.pedido_detalle.patrimonios.count()
        if self.instance.pk:
            # si estás editando, no sumes uno nuevo
            pass
        else:
            if ya_cargados >= self.pedido_detalle.cantidad:
                raise forms.ValidationError(
                    f"Ya cargaste {ya_cargados}/{self.pedido_detalle.cantidad} patrimonios para este item."
                )
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.pedido_detalle = self.pedido_detalle
        obj.asignado_por = self.user
        if commit:
            obj.save()
        return obj
