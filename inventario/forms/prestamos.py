from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from inventario.models import Prestamo, PrestamoDetalle, Item


class PrestamoForm(forms.ModelForm):
    class Meta:
        model = Prestamo
        fields = [
            "servicio",
            "entregado_a",
            "telefono_contacto",
            "fecha_retiro",
            "fecha_devolucion_estimada",
            "observaciones",
        ]
        widgets = {
            "fecha_retiro": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "fecha_devolucion_estimada": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 2, "placeholder": "Observaciones opcionales..."}),
            "entregado_a": forms.TextInput(attrs={"placeholder": "Nombre de quien retira"}),
            "telefono_contacto": forms.TextInput(attrs={"placeholder": "Teléfono (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and not self.initial.get("fecha_retiro"):
            self.initial["fecha_retiro"] = timezone.now().strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned = super().clean()
        fecha_retiro = cleaned.get("fecha_retiro")
        fecha_devolucion = cleaned.get("fecha_devolucion_estimada")
        if fecha_retiro and fecha_devolucion:
            retiro_date = timezone.localtime(fecha_retiro).date() if timezone.is_aware(fecha_retiro) else fecha_retiro.date()
            if fecha_devolucion < retiro_date:
                self.add_error(
                    "fecha_devolucion_estimada",
                    "La devolución estimada no puede ser anterior a la fecha de retiro.",
                )
        return cleaned


class PrestamoDetalleForm(forms.ModelForm):
    class Meta:
        model = PrestamoDetalle
        fields = ["item", "cantidad", "detalle"]
        widgets = {
            "detalle": forms.TextInput(attrs={"placeholder": "Detalle (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = Item.objects.filter(prestable=True).select_related(
            "toner", "articulo", "activo_pc", "impresora"
        )
        self.fields["item"].required = False
        self.fields["cantidad"].initial = 1

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get("item")
        cantidad = cleaned.get("cantidad")
        if item and (not cantidad or cantidad < 1):
            self.add_error("cantidad", "Ingresá una cantidad mayor a 0.")
        return cleaned


PrestamoDetalleFormSet = inlineformset_factory(
    Prestamo,
    PrestamoDetalle,
    form=PrestamoDetalleForm,
    extra=2,
    can_delete=True,
)
