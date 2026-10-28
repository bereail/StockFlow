from django import forms
from django.forms import inlineformset_factory

from ..models import Nota, NotaDetalle, Item, Pedido


class NotaForm(forms.ModelForm):
    pedido = forms.ModelChoiceField(
        label="Pedido asociado",
        queryset=Pedido.objects.order_by("-creado"),
        required=False,
        widget=forms.Select(attrs={"id": "id_pedido", "data-limite-inicial": "3"}),
        help_text="Si la nota corresponde a un pedido ya cargado, elegilo y se cargan sus ítems automáticamente.",
    )

    class Meta:
        model = Nota
        fields = ["numero", "servicio_solicitante", "fecha", "estado", "detalle", "notas_relacionadas"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "detalle": forms.Textarea(attrs={"rows": 3, "placeholder": "Detalle general de la nota..."}),
            "numero": forms.TextInput(attrs={"placeholder": "N° de nota (opcional)"}),
            "notas_relacionadas": forms.SelectMultiple(attrs={"data-limite-inicial": "3"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        qs_relacionadas = Nota.objects.select_related("servicio_solicitante").order_by("-fecha", "-creado")
        if self.instance.pk:
            qs_relacionadas = qs_relacionadas.exclude(pk=self.instance.pk)
        self.fields["notas_relacionadas"].queryset = qs_relacionadas
        self.fields["notas_relacionadas"].required = False
        self.fields["notas_relacionadas"].label_from_instance = (
            lambda n: f"{n.numero.strip() or 'Sin número'} — {getattr(n.servicio_solicitante, 'nombre', None) or 'Sin servicio'} ({n.get_estado_display()})"
        )

        self.fields["pedido"].empty_label = "— Sin pedido asociado —"
        self.fields["pedido"].label_from_instance = lambda p: f"{p.numero} ({p.get_estado_display()})"

        # Al editar, mostramos el pedido ya vinculado (si hay).
        if self.instance.pk:
            pedido_vinculado = self.instance.pedidos.first()
            if pedido_vinculado:
                self.fields["pedido"].initial = pedido_vinculado.pk


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
