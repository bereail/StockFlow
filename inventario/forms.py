from django import forms
from django.utils import timezone
from django.forms import inlineformset_factory
from .models import (
    Toner,
    Articulo,
    Documento,
    Movimiento,
    MovimientoDetalle,
    Prestamo,
    PrestamoDetalle,
    Item
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


    Prestamo,
    PrestamoDetalle,
    fields=["item", "cantidad", "detalle"],
    extra=1,
    can_delete=True,
    widgets={
        "detalle": forms.TextInput(attrs={"placeholder": "Detalle opcional (ej: con control, con cargador...)"}),
    }

ITEM_CHOICES = [
    ("PROYECTOR", "Proyector"),
    ("WEBCAM", "Cámara web"),
    ("NOTEBOOK", "Notebook"),
    ("PROLONGACION", "Prolongación"),
]


class PrestamoForm(forms.ModelForm):
    items = forms.MultipleChoiceField(
        choices=ITEM_CHOICES,
        required=True,
        widget=forms.CheckboxSelectMultiple,
        label="Ítems a solicitar",
    )

    class Meta:
        model = Prestamo
        fields = [
            "servicio",
            "telefono_contacto",
            "fecha_retiro",
            "fecha_devolucion_estimada",
            "entregado_a",
            "items",           # ✅ IMPORTANTÍSIMO
            "observaciones",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Precargar checks si editás
        selected = []
        if self.instance and self.instance.pk:
            if self.instance.proyector:
                selected.append("PROYECTOR")
            if self.instance.camara_web:
                selected.append("WEBCAM")
            if self.instance.notebook:
                selected.append("NOTEBOOK")
            if self.instance.prolongacion:
                selected.append("PROLONGACION")

        self.fields["items"].initial = selected

    def clean_items(self):
        items = self.cleaned_data.get("items") or []
        if len(items) == 0:
            raise forms.ValidationError("Seleccioná al menos un ítem.")
        return items

    def save(self, commit=True):
        obj = super().save(commit=False)
        items = set(self.cleaned_data.get("items") or [])

        obj.proyector = "PROYECTOR" in items
        obj.camara_web = "WEBCAM" in items
        obj.notebook = "NOTEBOOK" in items
        obj.prolongacion = "PROLONGACION" in items

        if commit:
            obj.save()
        return obj