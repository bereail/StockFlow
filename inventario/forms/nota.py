from django import forms
from django.forms import inlineformset_factory

from ..models import Nota, NotaDetalle, Item


class NotaForm(forms.ModelForm):
    class Meta:
        model = Nota
        fields = ["numero", "servicio_solicitante", "fecha", "estado", "detalle"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "detalle": forms.Textarea(attrs={"rows": 3, "placeholder": "Detalle general de la nota..."}),
            "numero": forms.TextInput(attrs={"placeholder": "N° de nota (opcional)"}),
        }


class NotaDetalleForm(forms.ModelForm):
    class Meta:
        model = NotaDetalle
        fields = ["item", "cantidad", "detalle"]
        widgets = {"detalle": forms.TextInput(attrs={"placeholder": "Detalle (opcional)"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # El item nunca es toner
        self.fields["item"].queryset = Item.objects.exclude(tipo="TONER")
        self.fields["item"].required = False

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get("item")
        cantidad = cleaned.get("cantidad")
        detalle = (cleaned.get("detalle") or "").strip()

        if not item and not detalle:
            raise forms.ValidationError("Elegí un item o escribí un detalle en el renglón.")

        if item and (cantidad is None or cantidad <= 0):
            self.add_error("cantidad", "Ingresá una cantidad mayor a 0.")

        return cleaned


NotaDetalleFormSet = inlineformset_factory(
    Nota,
    NotaDetalle,
    form=NotaDetalleForm,
    extra=1,
    can_delete=True
)