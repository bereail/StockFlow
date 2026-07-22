from django import forms
from inventario.models import Articulo, PatrimonioUnidad
from django.utils import timezone
from inventario.models import Servicio
from ..services.items import item_de_articulo

class ArticuloForm(forms.ModelForm):
    class Meta:
        model = Articulo
        fields = ["nombre", "activo", "marca", "descripcion", "caracteristicas", "observaciones", "es_patrimonial", "genera_ficha"]
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
        self.fields["es_patrimonial"].required = False
        self.fields["genera_ficha"].required = False

    def save(self, commit=True):
        articulo = super().save(commit=commit)
        if commit:
            # Todo artículo necesita su Item correspondiente para poder
            # elegirlo como ítem de un pedido (igual que las impresoras).
            item_de_articulo(articulo)
        return articulo

class EntregaRapidaArticuloForm(forms.Form):
    servicio = forms.ModelChoiceField(queryset=Servicio.objects.order_by("nombre"))
    articulo = forms.ModelChoiceField(queryset=Articulo.objects.filter(activo=True).order_by("marca", "nombre"))
    cantidad = forms.IntegerField(min_value=1, initial=1)

    unidad_patrimonial = forms.ModelChoiceField(
        queryset=PatrimonioUnidad.objects.select_related("articulo").order_by("numero_patrimonio"),
        required=False,
        label="Unidad patrimonial (opcional)",
        help_text="Elegí una unidad puntual solo si el artículo es patrimonial y sabés cuál se entrega.",
    )

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
        self.fields["unidad_patrimonial"].empty_label = "-- Genérico / no aplica --"

    def clean(self):
        cleaned = super().clean()
        unidad = cleaned.get("unidad_patrimonial")
        articulo = cleaned.get("articulo")
        cantidad = cleaned.get("cantidad")

        if unidad and articulo and unidad.articulo_id != articulo.id:
            self.add_error("unidad_patrimonial", "Esa unidad no pertenece al artículo elegido.")
        if unidad and cantidad and cantidad != 1:
            self.add_error("cantidad", "Si elegís una unidad puntual, la cantidad debe ser 1.")

        return cleaned