from django import forms
from django.utils import timezone
from ..models import AsignacionImpresora


class AsignacionImpresoraForm(forms.ModelForm):
    class Meta:
        model = AsignacionImpresora
        fields = [
            "servicio",
            "fecha_desde",
            "ubicacion",
            "responsable",
            "observaciones",
        ]
        widgets = {
            "fecha_desde": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        self.impresora = kwargs.pop("impresora", None)
        super().__init__(*args, **kwargs)

        # default fecha hoy
        if not self.initial.get("fecha_desde"):
            self.initial["fecha_desde"] = timezone.localdate()

        # opcionales
        for f in ["ubicacion", "responsable", "observaciones"]:
            if f in self.fields:
                self.fields[f].required = False

    def save(self, commit=True):
        asignacion = super().save(commit=False)

        if self.impresora:
            asignacion.impresora = self.impresora

        if commit:
            # 🔥 cerrar asignación activa anterior
            activa = (
                self.impresora.asignaciones
                .filter(fecha_hasta__isnull=True)
                .order_by("-fecha_desde")
                .first()
            )

            if activa:
                activa.fecha_hasta = timezone.localdate()
                activa.save()

            asignacion.save()

        return asignacion