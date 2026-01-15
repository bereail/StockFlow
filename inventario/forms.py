from django import forms
from django.utils import timezone

from .models import (
    Toner,
    Articulo,
    Servicio,
    Documento,
    Movimiento,
    MovimientoDetalle,
    ActivoPC,
    Impresora,
    PrestamoProyector,
    Pendiente, 
    Reparacion,
    Proveedor
)


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

# =========================
# TONER
# =========================
class TonerForm(forms.ModelForm):
    class Meta:
        model = Toner
        fields = ["nombre", "activo", "marca", "modelo_impresora"]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Ej: CE285A / 12A"}),
            "marca": forms.TextInput(attrs={"placeholder": "HP (opcional)"}),
            "modelo_impresora": forms.TextInput(attrs={"placeholder": "Ej: P1102 / M401 (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["marca"].required = False
        self.fields["modelo_impresora"].required = False


# =========================
# ARTICULO
# =========================
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


# =========================
# DOCUMENTO
# (opcional: si lo querés CRUD separado)
# =========================
class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = ["tipo", "numero", "fecha", "observaciones"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "numero": forms.TextInput(attrs={"placeholder": "Ej: 1234"}),
            "observaciones": forms.Textarea(attrs={"rows": 2, "placeholder": "Obs (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha"].required = False
        self.fields["observaciones"].required = False


# =========================
# MOVIMIENTO (CABECERA)
# =========================
from django import forms
from django.utils import timezone

from .models import (
    Toner,
    Articulo,
    Servicio,
    Documento,
    Movimiento,
    MovimientoDetalle,
)


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

# =========================
# TONER
# =========================
class TonerForm(forms.ModelForm):
    class Meta:
        model = Toner
        fields = ["nombre", "activo", "marca", "modelo_impresora"]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Ej: CE285A / 12A"}),
            "marca": forms.TextInput(attrs={"placeholder": "HP (opcional)"}),
            "modelo_impresora": forms.TextInput(attrs={"placeholder": "Ej: P1102 / M401 (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["marca"].required = False
        self.fields["modelo_impresora"].required = False


# =========================
# ARTICULO
# =========================
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


# =========================
# DOCUMENTO
# (opcional: si lo querés CRUD separado)
# =========================
class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = ["tipo", "numero", "fecha", "observaciones"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "numero": forms.TextInput(attrs={"placeholder": "Ej: 1234"}),
            "observaciones": forms.Textarea(attrs={"rows": 2, "placeholder": "Obs (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha"].required = False
        self.fields["observaciones"].required = False


# =========================
# MOVIMIENTO (CABECERA)
# =========================
class MovimientoForm(forms.ModelForm):
    class Meta:
        model = Movimiento
        fields = ["tipo", "servicio", "fecha", "documento", "observaciones"]
        widgets = {
            "fecha": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "observaciones": forms.Textarea(attrs={"rows": 2, "placeholder": "Observaciones (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["servicio"].required = False
        self.fields["fecha"].required = False
        self.fields["observaciones"].required = False

        # Default fecha
        if not self.instance.pk and not self.initial.get("fecha"):
            self.initial["fecha"] = timezone.now().strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        servicio = cleaned.get("servicio")

        if tipo == "EGRESO" and not servicio:
            self.add_error("servicio", "En un EGRESO debe seleccionar un servicio.")

        # Regla: en INGRESO, servicio vacío
        if tipo == "INGRESO":
            cleaned["servicio"] = None

        return cleaned


# =========================
# DETALLES (formsets)
# MovimientoDetalle -> elegís toner/articulo y cantidad
# =========================

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

class MovimientoDetalleTonerForm(forms.ModelForm):
    toner = forms.ModelChoiceField(
        queryset=Toner.objects.filter(activo=True),
        required=False,
        empty_label="-- seleccionar toner --",
    )

    class Meta:
        model = MovimientoDetalle
        fields = ["toner", "cantidad"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cantidad"].required = False

    def clean(self):
        cleaned = super().clean()
        toner = cleaned.get("toner")
        cantidad = cleaned.get("cantidad")

        # Fila vacía => OK
        if not toner and not cantidad:
            return cleaned

        if toner and not cantidad:
            self.add_error("cantidad", "Ingresá cantidad.")
        if cantidad and not toner:
            self.add_error("toner", "Seleccioná un toner.")

        return cleaned


class MovimientoDetalleArticuloForm(forms.ModelForm):
    articulo = forms.ModelChoiceField(
        queryset=Articulo.objects.filter(activo=True),
        required=False,
        empty_label="-- seleccionar artículo --",
    )

    class Meta:
        model = MovimientoDetalle
        fields = ["articulo", "cantidad"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cantidad"].required = False

    def clean(self):
        cleaned = super().clean()
        articulo = cleaned.get("articulo")
        cantidad = cleaned.get("cantidad")

        # Fila vacía => OK
        if not articulo and not cantidad:
            return cleaned

        if articulo and not cantidad:
            self.add_error("cantidad", "Ingresá cantidad.")
        if cantidad and not articulo:
            self.add_error("articulo", "Seleccioná un artículo.")

        return cleaned
    
# SERVICIOS #
class ServicioForm(forms.ModelForm):
    class Meta:
        model = Servicio
        fields = ["nombre", "descripcion"]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Ej: Terapia Intensiva"}),
            "descripcion": forms.Textarea(attrs={"rows": 3, "placeholder": "Opcional"}),
        }

# PCS #

class ActivoPCForm(forms.ModelForm):
    class Meta:
        model = ActivoPC
        fields = [
            "nombre_pc",
            "activo",
            "ip",
            "patrimonio",
            "serie",
            "caracteristicas",
            "observaciones",
            "servicio",
        ]
        widgets = {
            "nombre_pc": forms.TextInput(attrs={"placeholder": "Ej: PC Guardia 1 / PC Administración"}),
            "ip": forms.TextInput(attrs={"placeholder": "192.168.1.50 (opcional)"}),
            "patrimonio": forms.TextInput(attrs={"placeholder": "N° Patrimonio (opcional)"}),
            "serie": forms.TextInput(attrs={"placeholder": "N° Serie (opcional)"}),
            "caracteristicas": forms.Textarea(attrs={"rows": 2, "placeholder": "Características (opcional)"}),
            "observaciones": forms.Textarea(attrs={"rows": 2, "placeholder": "Observaciones (opcional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ip"].required = False
        self.fields["patrimonio"].required = False
        self.fields["serie"].required = False
        self.fields["caracteristicas"].required = False
        self.fields["observaciones"].required = False
        self.fields["servicio"].required = False

# IMPRESORAS #
class ImpresoraForm(forms.ModelForm):
    class Meta:
        model = Impresora
        fields = [
            "marca",
            "modelo",
            "tipo",
            "patrimonio",
            "activo",
            "estado",
            "servicio",
            "conexion",
            "ip",
            "toner",
            "observaciones",
        ]
        widgets = {
            "marca": forms.TextInput(attrs={"placeholder": "Ej: Ricoh / HP"}),
            "modelo": forms.TextInput(attrs={"placeholder": "Ej: MP 301"}),
            "tipo": forms.TextInput(attrs={"placeholder": "Ej: Multifunción"}),
            "patrimonio": forms.TextInput(attrs={"placeholder": "N° patrimonio (opcional)"}),
            "estado": forms.TextInput(attrs={"placeholder": "ACTIVA / BAJA / REPARACIÓN"}),
            "ip": forms.TextInput(attrs={"placeholder": "192.168.1.20"}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # campos opcionales
        self.fields["patrimonio"].required = False
        self.fields["estado"].required = False
        self.fields["servicio"].required = False
        self.fields["ip"].required = False
        self.fields["toner"].required = False
        self.fields["observaciones"].required = False


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
        # default para datetime-local
        if not self.initial.get("fecha"):
            self.initial["fecha"] = timezone.localtime(timezone.now()).strftime("%Y-%m-%dT%H:%M")


# PROYECTOR #
class PrestamoProyectorForm(forms.ModelForm):
    class Meta:
        model = PrestamoProyector
        fields = [
            "servicio",
            "telefono_contacto",
            "fecha_retiro",
            "fecha_devolucion_estimada",
            "incluye_prolongacion",
            "incluye_pc",
            "incluye_notebook",
            "observaciones",
        ]
        widgets = {
            "fecha_retiro": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "fecha_devolucion_estimada": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 2}),
            "telefono_contacto": forms.TextInput(attrs={"placeholder": "Ej: 381-xxxxxxx"}),
        }

# PENDIENTES #
class PendienteForm(forms.ModelForm):
    class Meta:
        model = Pendiente
        fields = ["texto", "servicio"]
        widgets = {
            "texto": forms.TextInput(attrs={
                "placeholder": "Anotar pendiente…",
                "autofocus": True,
            }),
        }

# REPARACION #
class ReparacionForm(forms.ModelForm):
    class Meta:
        model = Reparacion
        fields = [
            "item",
            "proveedor",
            "estado",
            "fecha_envio",
            "fecha_retorno",
            "diagnostico",
            "seguimiento",
        ]
        widgets = {
            "fecha_envio": forms.DateInput(attrs={"type": "date"}),
            "fecha_retorno": forms.DateInput(attrs={"type": "date"}),
            "diagnostico": forms.TextInput(attrs={"placeholder": "Ej: No imprime / atasca / error SC..."}),
            "seguimiento": forms.Textarea(attrs={"rows": 3, "placeholder": "Notas de seguimiento..."}),
        }