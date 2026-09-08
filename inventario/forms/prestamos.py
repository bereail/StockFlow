from django import forms
from django.forms import inlineformset_factory
from django.forms.models import BaseInlineFormSet
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


class PrestamoDetalleBaseFormSet(BaseInlineFormSet):
    """
    Evita que un mismo item físico (ej. un proyector) quede prestado en dos
    préstamos activos a la vez, y que se repita dentro del mismo préstamo.
    """
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        prestamo_actual = self.instance
        excluir_pk = prestamo_actual.pk if prestamo_actual and prestamo_actual.pk else None

        items_en_este_form = set()
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or not form.cleaned_data:
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            item = form.cleaned_data.get("item")
            if not item:
                continue

            if item.pk in items_en_este_form:
                form.add_error("item", f"«{item}» está repetido en este mismo préstamo.")
                continue
            items_en_este_form.add(item.pk)

            en_prestamo = PrestamoDetalle.objects.filter(
                item=item,
                prestamo__fecha_devolucion_real__isnull=True,
            )
            if excluir_pk:
                en_prestamo = en_prestamo.exclude(prestamo_id=excluir_pk)
            if en_prestamo.exists():
                form.add_error("item", f"«{item}» ya está prestado y todavía no fue devuelto.")


PrestamoDetalleFormSet = inlineformset_factory(
    Prestamo,
    PrestamoDetalle,
    form=PrestamoDetalleForm,
    formset=PrestamoDetalleBaseFormSet,
    extra=2,
    can_delete=True,
)
