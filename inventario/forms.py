from django import forms
from django.utils import timezone
from django.forms import inlineformset_factory
from .models import (
    Toner,
    Articulo,
    Documento,
    Movimiento,
    MovimientoDetalle,
    Pedido,
    PedidoDetalle,
    PatrimonioUnidad
)

class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = ["tipo", "numero", "fecha", "observaciones"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "numero": forms.TextInput(attrs={"placeholder": "Ej: 1234"}),
            "observaciones": forms.Textarea(attrs={"rows": 2, "placeholder": "Obs (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha"].required = False
        self.fields["observaciones"].required = False

class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = ["tipo", "numero", "fecha", "observaciones"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "numero": forms.TextInput(attrs={"placeholder": "Ej: 1234"}),
            "observaciones": forms.Textarea(attrs={"rows": 2, "placeholder": "Obs (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha"].required = False
        self.fields["observaciones"].required = False

class MovimientoForm(forms.ModelForm):
    class Meta:
        model = Movimiento
        fields = ["tipo", "servicio", "fecha", "documento", "observaciones"]
        widgets = {
            "fecha": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "observaciones": forms.Textarea(attrs={"rows": 2, "placeholder": "Observaciones (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["servicio"].required = False
        self.fields["fecha"].required = False
        self.fields["observaciones"].required = False

        # Default fecha
        if not self.instance.pk and not self.initial.get("fecha"):
            self.initial["fecha"] = timezone.now().strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        servicio = cleaned.get("servicio")

        if tipo == "EGRESO" and not servicio:
            self.add_error("servicio", "En un EGRESO debe seleccionar un servicio.")

        # Regla: en INGRESO, servicio vacío
        if tipo == "INGRESO":
            cleaned["servicio"] = None

        return cleaned

class MovimientoDetalleTonerForm(forms.ModelForm):
    toner = forms.ModelChoiceField(
        queryset=Toner.objects.filter(activo=True),
        required=False,
        empty_label="-- seleccionar toner --",
    )

    class Meta:
        model = MovimientoDetalle
        fields = ["toner", "cantidad"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cantidad"].required = False

    def clean(self):
        cleaned = super().clean()
        toner = cleaned.get("toner")
        cantidad = cleaned.get("cantidad")

        # Fila vacía => OK
        if not toner and not cantidad:
            return cleaned

        if toner and not cantidad:
            self.add_error("cantidad", "Ingresá cantidad.")
        if cantidad and not toner:
            self.add_error("toner", "Seleccioná un toner.")

        return cleaned

class MovimientoDetalleArticuloForm(forms.ModelForm):
    articulo = forms.ModelChoiceField(
        queryset=Articulo.objects.filter(activo=True),
        required=False,
        empty_label="-- seleccionar artículo --",
    )

    class Meta:
        model = MovimientoDetalle
        fields = ["articulo", "cantidad"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cantidad"].required = False

    def clean(self):
        cleaned = super().clean()
        articulo = cleaned.get("articulo")
        cantidad = cleaned.get("cantidad")

        # Fila vacía => OK
        if not articulo and not cantidad:
            return cleaned

        if articulo and not cantidad:
            self.add_error("cantidad", "Ingresá cantidad.")
        if cantidad and not articulo:
            self.add_error("articulo", "Seleccioná un artículo.")

        return cleaned

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
