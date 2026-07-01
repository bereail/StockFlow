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
            "proveedor",
            "numero_nota",
            "para_que",
            "observaciones",
            "estado",
            "fecha_aprobado",
            "fecha_recibido",
            "fecha_entregado",
        ]
        widgets = {
            "observaciones":    forms.Textarea(attrs={"rows": 2}),
            "para_que":         forms.TextInput(attrs={"placeholder": "Motivo / para qué"}),
            "numero":           forms.TextInput(attrs={"placeholder": "Ej: PED-2026-0001"}),
            "numero_nota":      forms.TextInput(attrs={"placeholder": "Opcional"}),
            "fecha_aprobado":   forms.DateInput(attrs={"type": "date"}),
            "fecha_recibido":   forms.DateInput(attrs={"type": "date"}),
            "fecha_entregado":  forms.DateInput(attrs={"type": "date"}),
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
        self.fields["item"].queryset = (
            Item.objects
            .filter(tipo__in=["ARTICULO", "IMPRESORA"])
            .select_related("articulo", "impresora")
            .order_by("tipo", "articulo__nombre", "impresora__marca", "impresora__modelo")
        )
        self.fields["item"].label_from_instance = lambda obj: (
            obj.articulo.nombre if obj.articulo
            else f"Impresora: {obj.impresora}" if obj.impresora
            else str(obj)
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
            "nombre_pc",
            "ip",
            "usuario_asignado",
            "serial",
            "observaciones",
            "servicio_asignado",
        ]
        widgets = {
            "detalle_item":     forms.TextInput(attrs={"placeholder": "Ej: PC Dell OptiPlex 3000"}),
            "nombre_pc":        forms.TextInput(attrs={"placeholder": "Ej: HEEP-PC-042  (opcional)"}),
            "ip":               forms.TextInput(attrs={"placeholder": "Ej: 192.168.1.42  (opcional)"}),
            "usuario_asignado": forms.TextInput(attrs={"placeholder": "Nombre del usuario  (opcional)"}),
            "observaciones":    forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, pedido_detalle=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pedido_detalle = pedido_detalle
        self.user = user

        item = pedido_detalle.item if pedido_detalle else None
        self.es_impresora = bool(item and item.tipo == "IMPRESORA")

        # Al cargar el patrimonio de una impresora, precargamos los datos
        # que ya tiene el catálogo (marca/modelo/IP/nº patrimonio) para que
        # solo haya que personalizar lo que cambia por unidad.
        if self.es_impresora and self.instance.pk is None:
            impresora = item.impresora
            self.fields["detalle_item"].initial = f"{impresora.marca} {impresora.modelo}"
            if impresora.patrimonio:
                self.fields["numero_patrimonio"].initial = impresora.patrimonio
            if impresora.ip:
                self.fields["ip"].initial = impresora.ip
            if impresora.servicio_actual:
                self.fields["servicio_asignado"].initial = impresora.servicio_actual

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
