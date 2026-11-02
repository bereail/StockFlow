from django import forms
from inventario.models import Impresora, Toner, Articulo
from django.utils import timezone
from ..models import Servicio
from ..services.items import item_de_impresora, item_de_articulo
from ..services.impresoras import asignar_impresora_a_servicio

class ImpresoraForm(forms.ModelForm):
    class Meta:
        model = Impresora
        fields = [
            "articulo",
            "marca",
            "modelo",
            "tipo",
            "patrimonio",
            "propiedad",
            "empresa_externa",
            "activo",
            "estado",
            "conexion",
            "ip",
            "mac",
            "submascara",
            "puerta_enlace",
            "dns",
            "toner",
            "observaciones",
        ]
        widgets = {
            "marca": forms.TextInput(attrs={"placeholder": "Ej: Ricoh / HP"}),
            "modelo": forms.TextInput(attrs={"placeholder": "Ej: MP 301"}),
            "tipo": forms.TextInput(attrs={"placeholder": "Ej: Multifunción / Láser / Inkjet (opcional)"}),
            "patrimonio": forms.TextInput(attrs={"placeholder": "N° patrimonio (opcional)"}),
            "empresa_externa": forms.TextInput(attrs={"placeholder": "Ej: Xerox Rental (solo si es externa)"}),
            "estado": forms.TextInput(attrs={"placeholder": "ACTIVA / BAJA / REPARACIÓN"}),
            "ip": forms.TextInput(attrs={"placeholder": "192.168.1.20"}),
            "mac": forms.TextInput(attrs={"placeholder": "00:1A:2B:3C:4D:5E (opcional)"}),
            "submascara": forms.TextInput(attrs={"placeholder": "255.255.255.0 (opcional)"}),
            "puerta_enlace": forms.TextInput(attrs={"placeholder": "192.168.1.1 (opcional)"}),
            "dns": forms.TextInput(attrs={"placeholder": "8.8.8.8, 8.8.4.4 (opcional)"}),
            "observaciones": forms.Textarea(attrs={"rows": 2, "placeholder": "Obs (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ✅ opcionales (sin KeyError)
        for f in ["patrimonio", "empresa_externa", "estado", "ip", "mac", "submascara", "puerta_enlace", "dns", "toner", "observaciones", "articulo", "tipo"]:
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
                Articulo.objects.filter(es_patrimonial=True, genera_ficha="IMPRESORA").order_by("nombre")
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

        if cleaned.get("propiedad") == "EXTERNA" and not cleaned.get("empresa_externa"):
            self.add_error("empresa_externa", "Si la impresora es de una empresa externa, indicá cuál.")
        return cleaned

    def save(self, commit=True):
        impresora = super().save(commit=commit)
        if commit:
            # Toda impresora necesita su Item correspondiente para poder
            # elegirla como ítem de un pedido.
            item_de_impresora(impresora)
        return impresora


class ModeloImpresoraForm(forms.ModelForm):
    """
    Catálogo de "modelos" de impresora (ej: "Brother HL 1212"), para elegir
    al dar de alta una impresora nueva en vez de tipear marca/modelo a mano
    cada vez. Es el mismo Articulo patrimonial de siempre, solo que acá se
    fuerzan es_patrimonial=True y genera_ficha="IMPRESORA" sin mostrárselos
    al usuario, para no obligarlo a pasar por la sección de Artículos.
    """
    class Meta:
        model = Articulo
        fields = ["nombre", "marca", "caracteristicas", "observaciones"]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Ej: HL 1212 / LaserJet Pro M404"}),
            "marca": forms.TextInput(attrs={"placeholder": "Ej: Brother / HP"}),
            "caracteristicas": forms.Textarea(attrs={"rows": 2, "placeholder": "Características (opcional)"}),
            "observaciones": forms.Textarea(attrs={"rows": 2, "placeholder": "Obs (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["marca"].required = False
        self.fields["caracteristicas"].required = False
        self.fields["observaciones"].required = False

    def save(self, commit=True):
        articulo = super().save(commit=False)
        articulo.es_patrimonial = True
        articulo.genera_ficha = "IMPRESORA"
        if not articulo.nombre.strip().lower().startswith("impresora"):
            articulo.nombre = f"Impresora {articulo.nombre}".strip()
        if commit:
            articulo.save()
            item_de_articulo(articulo)
        return articulo


class ImpresoraCreateForm(forms.ModelForm):
    """
    Alta de una impresora NUEVA: a diferencia de ImpresoraForm (que se sigue
    usando para editar impresoras viejas con marca/modelo en texto libre),
    acá el modelo de catálogo es obligatorio — marca/modelo salen de ahí, no
    se tipean a mano — y se puede asignar el servicio en el mismo paso.
    """
    servicio = forms.ModelChoiceField(
        queryset=Servicio.objects.order_by("nombre"),
        required=False,
        label="Servicio",
        help_text="Asignación inicial (opcional, se puede hacer después).",
    )

    class Meta:
        model = Impresora
        fields = [
            "articulo",
            "tipo",
            "patrimonio",
            "propiedad",
            "empresa_externa",
            "conexion",
            "ip",
            "mac",
            "submascara",
            "puerta_enlace",
            "dns",
            "toner",
            "observaciones",
        ]
        widgets = {
            "tipo": forms.TextInput(attrs={"placeholder": "Ej: Multifunción / Láser / Inkjet (opcional)"}),
            "patrimonio": forms.TextInput(attrs={"placeholder": "N° patrimonio (opcional)"}),
            "empresa_externa": forms.TextInput(attrs={"placeholder": "Ej: Xerox Rental (solo si es externa)"}),
            "ip": forms.TextInput(attrs={"placeholder": "192.168.1.20"}),
            "mac": forms.TextInput(attrs={"placeholder": "00:1A:2B:3C:4D:5E (opcional)"}),
            "submascara": forms.TextInput(attrs={"placeholder": "255.255.255.0 (opcional)"}),
            "puerta_enlace": forms.TextInput(attrs={"placeholder": "192.168.1.1 (opcional)"}),
            "dns": forms.TextInput(attrs={"placeholder": "8.8.8.8, 8.8.4.4 (opcional)"}),
            "observaciones": forms.Textarea(attrs={"rows": 2, "placeholder": "Obs (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ["tipo", "patrimonio", "empresa_externa", "mac", "submascara", "puerta_enlace", "dns", "toner", "observaciones"]:
            if f in self.fields:
                self.fields[f].required = False

        self.fields["toner"].queryset = Toner.objects.filter(activo=True).order_by("marca", "nombre")
        self.fields["toner"].empty_label = "-- Sin toner / No aplica --"

        self.fields["articulo"].queryset = (
            Articulo.objects.filter(es_patrimonial=True, genera_ficha="IMPRESORA").order_by("nombre")
        )
        self.fields["articulo"].required = True
        self.fields["articulo"].empty_label = None
        self.fields["articulo"].label = "Modelo de impresora"
        self.fields["articulo"].help_text = (
            "Si no ves tu modelo, cargalo primero con \"+ Nuevo modelo\"."
        )

    def clean(self):
        cleaned = super().clean()
        conexion = cleaned.get("conexion")
        ip = cleaned.get("ip")
        if conexion == "IP" and not ip:
            self.add_error("ip", "Si la conexión es por red (IP), debés cargar la IP.")

        if cleaned.get("propiedad") == "EXTERNA" and not cleaned.get("empresa_externa"):
            self.add_error("empresa_externa", "Si la impresora es de una empresa externa, indicá cuál.")
        return cleaned

    def save(self, commit=True):
        impresora = super().save(commit=False)
        articulo = self.cleaned_data["articulo"]
        impresora.marca = articulo.marca or articulo.nombre
        impresora.modelo = articulo.nombre
        if commit:
            impresora.save()
            item_de_impresora(impresora)
            servicio = self.cleaned_data.get("servicio")
            if servicio:
                asignar_impresora_a_servicio(impresora, servicio)
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