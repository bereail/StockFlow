from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone
from ..models import Pedido, PedidoDetalle, PatrimonioUnidad
from ..models import Item  # ✅ IMPORTANTE

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

        # Regla: no crear un pedido directamente como ENTREGADO
        if estado == "ENTREGADO" and self.instance.pk is None:
            raise forms.ValidationError("No podés crear un pedido directamente como ENTREGADO.")

        return cleaned

class PedidoDetalleForm(forms.ModelForm):
    class Meta:
        model = PedidoDetalle
        fields = ["item", "cantidad", "detalle"]
        widgets = {
            "detalle": forms.TextInput(attrs={"placeholder": "Detalle opcional (marca/modelo/etc.)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ✅ SOLO ARTICULOS (sin toners)
        self.fields["item"].queryset = (
            Item.objects
            .filter(tipo="ARTICULO")  # <-- si tu choice es distinto, cambiá este string
            .order_by("id")
        )

PedidoDetalleFormSet = inlineformset_factory(
    Pedido,
    PedidoDetalle,
    form=PedidoDetalleForm,  # <-- clave
    extra=1,
    can_delete=True,
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
            "detalle_item": forms.TextInput(attrs={"placeholder": "Detalle libre (ej: PC Dell...)"}),
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

        ya_cargados = self.pedido_detalle.patrimonios.count()

        # Si es creación (no edición), validar cupo
        if not self.instance.pk and ya_cargados >= self.pedido_detalle.cantidad:
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
