from django import forms
from django.utils import timezone
from .models import (
    Documento,
    Movimiento,
    MovimientoDetalle,
    Toner,
    Articulo,
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

        if not self.instance.pk and not self.initial.get("fecha"):
            self.initial["fecha"] = timezone.now().strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        servicio = cleaned.get("servicio")

        if tipo == "EGRESO" and not servicio:
            self.add_error("servicio", "En un EGRESO debe seleccionar un servicio.")

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

        if not articulo and not cantidad:
            return cleaned

        if articulo and not cantidad:
            self.add_error("cantidad", "Ingresá cantidad.")
        if cantidad and not articulo:
            self.add_error("articulo", "Seleccioná un artículo.")

        return cleaned
