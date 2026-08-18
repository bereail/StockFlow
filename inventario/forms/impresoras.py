from django import forms
from inventario.models import Impresora, Toner, Articulo
from django.utils import timezone
from ..models import Servicio
from ..services.items import item_de_impresora

class ImpresoraForm(forms.ModelForm):
    class Meta:
        model = Impresora
        fields = [
            "articulo",
            "marca",
            "modelo",
            "tipo",
            "patrimonio",
            "activo",
            "estado",
            "conexion",
            "ip",
            "submascara",
            "puerta_enlace",
            "dns",
            "toner",
            "observaciones",
        ]
        widgets = {
            "marca": forms.TextInput(attrs={"placeholder": "Ej: Ricoh / HP"}),
            "modelo": forms.TextInput(attrs={"placeholder": "Ej: MP 301"}),
            "tipo": forms.TextInput(attrs={"placeholder": "Ej: Multifunción / Láser / Inkjet"}),
            "patrimonio": forms.TextInput(attrs={"placeholder": "N° patrimonio (opcional)"}),
            "estado": forms.TextInput(attrs={"placeholder": "ACTIVA / BAJA / REPARACIÓN"}),
            "ip": forms.TextInput(attrs={"placeholder": "192.168.1.20"}),
            "submascara": forms.TextInput(attrs={"placeholder": "255.255.255.0 (opcional)"}),
            "puerta_enlace": forms.TextInput(attrs={"placeholder": "192.168.1.1 (opcional)"}),
            "dns": forms.TextInput(attrs={"placeholder": "8.8.8.8, 8.8.4.4 (opcional)"}),
            "observaciones": forms.Textarea(attrs={"rows": 2, "placeholder": "Obs (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ✅ opcionales (sin KeyError)
        for f in ["patrimonio", "estado", "ip", "submascara", "puerta_enlace", "dns", "toner", "observaciones", "articulo"]:
            if f in self.fields:
                self.fields[f].required = False

        # ✅ TONER opcional: solo activos + ordenado + label vacío
        if "toner" in self.fields:
            self.fields["toner"].queryset = Toner.objects.filter(activo=True).order_by("marca", "nombre")
            self.fields["toner"].empty_label = "-- Sin toner / No aplica --"

        # ✅ ARTICULO: solo el catálogo patrimonial (ahí es donde ya cargaste
        # cosas como "Impresora Brother HL 1212"), para vincular esta unidad
        # física a su tipo de catálogo.
        if "articulo" in self.fields:
            self.fields["articulo"].queryset = (
                Articulo.objects.filter(es_patrimonial=True).order_by("nombre")
            )
            self.fields["articulo"].empty_label = "-- Sin artículo de catálogo --"
            self.fields["articulo"].label = "Artículo de catálogo (patrimonial)"

    def clean(self):
        cleaned = super().clean()
        conexion = cleaned.get("conexion")
        ip = cleaned.get("ip")

        # ✅ regla: si es IP, debe tener IP
        if conexion == "IP" and not ip:
            self.add_error("ip", "Si la conexión es por red (IP), debés cargar la IP.")
        return cleaned

    def save(self, commit=True):
        impresora = super().save(commit=commit)
        if commit:
            # Toda impresora necesita su Item correspondiente para poder
            # elegirla como ítem de un pedido.
            item_de_impresora(impresora)
        return impresora


class EntregaRapidaImpresoraForm(forms.Form):
    servicio = forms.ModelChoiceField(
        queryset=Servicio.objects.order_by("nombre"),
        label="Servicio"
    )
    impresora = forms.ModelChoiceField(
        queryset=Impresora.objects.order_by("marca", "modelo"),
        label="Impresora"
    )
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2})
    )
    fecha = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get("fecha"):
            self.initial["fecha"] = timezone.localtime(timezone.now()).strftime("%Y-%m-%dT%H:%M")