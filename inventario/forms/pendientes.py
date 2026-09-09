from django import forms
from inventario.models import Pendiente


class PendienteForm(forms.ModelForm):
    class Meta:
        model = Pendiente
        fields = ["texto", "fecha_limite", "servicio", "pedido", "nota", "observacion"]
        widgets = {
            "texto": forms.TextInput(attrs={
                "placeholder": "Describí la tarea pendiente…",
                "autofocus": True,
            }),
            "fecha_limite": forms.DateInput(attrs={"type": "date"}),
            "observacion": forms.Textarea(attrs={"rows": 2, "placeholder": "Observaciones (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pedido"].queryset = self.fields["pedido"].queryset.order_by("-creado")
        self.fields["pedido"].empty_label = "Sin pedido vinculado"
        self.fields["pedido"].required = False
        self.fields["nota"].queryset = (
            self.fields["nota"].queryset
            .select_related("servicio_solicitante")
            .order_by("-fecha", "-creado")
        )
        self.fields["nota"].empty_label = "Sin nota vinculada"
        self.fields["nota"].required = False
