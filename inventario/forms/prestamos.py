from django import forms
from django.utils import timezone

from inventario.models import Prestamo

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
            "entregado_a",
            "fecha_retiro",
            "fecha_devolucion_estimada",
            "items",  # ✅ CLAVE
            "observaciones",
        ]
        widgets = {
            "fecha_retiro": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "fecha_devolucion_estimada": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # default fecha_retiro
        if not self.instance.pk and not self.initial.get("fecha_retiro"):
            self.initial["fecha_retiro"] = timezone.now()

        # precargar checks si editás
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
        if not items:
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
