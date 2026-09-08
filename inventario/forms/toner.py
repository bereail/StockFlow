from django import forms
from ..models import Toner, Servicio
from django.utils import timezone



class TonerForm(forms.ModelForm):
    class Meta:
        model = Toner
        fields = ["nombre", "activo", "marca", "modelo_impresora", "stock_minimo"]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Ej: CE285A / 12A"}),
            "marca": forms.TextInput(attrs={"placeholder": "HP (opcional)"}),
            "modelo_impresora": forms.TextInput(attrs={"placeholder": "Ej: P1102 / M401 (opcional)"}),
            "stock_minimo": forms.NumberInput(attrs={"min": 0, "placeholder": "0 = sin alerta"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["marca"].required = False
        self.fields["modelo_impresora"].required = False
        self.fields["stock_minimo"].required = False


class EntregaRapidaTonerForm(forms.Form):
    servicio = forms.ModelChoiceField(queryset=Servicio.objects.order_by("nombre"))
    toner = forms.ModelChoiceField(queryset=Toner.objects.filter(activo=True).order_by("marca", "nombre"))
    cantidad = forms.IntegerField(min_value=1, initial=1)


    observaciones = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    fecha = forms.DateTimeField(
        required=False,
        initial=timezone.now,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )