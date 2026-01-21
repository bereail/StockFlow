from django import forms
from inventario.models import Articulo
from django.utils import timezone
from inventario.models import Servicio

class ArticuloForm(forms.ModelForm):
    class Meta:
        model = Articulo
        fields = ["nombre", "activo", "marca", "descripcion", "caracteristicas", "observaciones"]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Cable USB / Mouse / Resma A4"}),
            "marca": forms.TextInput(attrs={"placeholder": "Genérica / HP / Logitech (opcional)"}),
            "descripcion": forms.Textarea(attrs={"rows": 2, "placeholder": "Descripción (opcional)"}),
            "caracteristicas": forms.Textarea(attrs={"rows": 2, "placeholder": "Características (opcional)"}),
            "observaciones": forms.Textarea(attrs={"rows": 2, "placeholder": "Obs (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["marca"].required = False
        self.fields["descripcion"].required = False
        self.fields["caracteristicas"].required = False
        self.fields["observaciones"].required = False

class EntregaRapidaArticuloForm(forms.Form):
    servicio = forms.ModelChoiceField(queryset=Servicio.objects.order_by("nombre"))
    articulo = forms.ModelChoiceField(queryset=Articulo.objects.filter(activo=True).order_by("marca", "nombre"))
    cantidad = forms.IntegerField(min_value=1, initial=1)

    observaciones = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    fecha = forms.DateTimeField(
        required=False,
        initial=timezone.now,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Para que el datetime-local muestre bien el default
        if not self.initial.get("fecha"):
            self.initial["fecha"] = timezone.now().strftime("%Y-%m-%dT%H:%M")