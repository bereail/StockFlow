from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv46_address
from ..models import Pedido, PedidoDetalle, PatrimonioUnidad, Nota
from ..models import Item  # ✅ IMPORTANTE
from ..services.impresoras import asignar_impresora_a_servicio
from ..services.patrimonios import generar_ficha_desde_articulo

class PedidoForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = [
            "numero",
            "servicios",
            "proveedor",
            "nota",
            "para_que",
            "observaciones",
            "estado",
            "fecha_aprobado",
            "fecha_recibido",
            "fecha_entregado",
        ]
        widgets = {
            "observaciones":    forms.Textarea(attrs={"rows": 2}),
            "para_que":         forms.TextInput(attrs={"placeholder": "Motivo / para qué"}),
            "numero":           forms.TextInput(attrs={"placeholder": "Ej: PED-2026-0001"}),
            "fecha_aprobado":   forms.DateInput(attrs={"type": "date"}),
            "fecha_recibido":   forms.DateInput(attrs={"type": "date"}),
            "fecha_entregado":  forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nota"].queryset = Nota.objects.select_related("servicio_solicitante").order_by("-fecha", "-creado")
        self.fields["nota"].required = False
        self.fields["nota"].empty_label = "— Sin nota asociada —"
        self.fields["nota"].label_from_instance = (
            lambda n: f"{n.numero.strip() or 'Sin número'} — {getattr(n.servicio_solicitante, 'nombre', None) or 'Sin servicio'} ({n.get_estado_display()})"
        )

    def clean(self):
        cleaned = super().clean()
        estado = cleaned.get("estado")

        # Regla: no crear un pedido directamente como ENTREGADO
        if estado == "ENTREGADO" and self.instance.pk is None:
            raise forms.ValidationError("No podés crear un pedido directamente como ENTREGADO.")

        return cleaned

class PedidoDetalleForm(forms.ModelForm):
    class Meta:
        model = PedidoDetalle
        fields = ["item", "cantidad", "detalle"]
        widgets = {
            "detalle": forms.TextInput(attrs={"placeholder": "Detalle opcional (marca/modelo/etc.)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = (
            Item.objects
            .filter(tipo__in=["ARTICULO", "IMPRESORA"])
            .select_related("articulo", "impresora")
            .order_by("tipo", "articulo__nombre", "impresora__marca", "impresora__modelo")
        )

        def _label(obj):
            if obj.articulo:
                nombre = str(obj.articulo)
                if obj.articulo.es_patrimonial:
                    return f"{nombre}  🔖 Patrimonial"
                return nombre
            if obj.impresora:
                return f"Impresora: {obj.impresora}"
            return str(obj)

        self.fields["item"].label_from_instance = _label

PedidoDetalleFormSet = inlineformset_factory(
    Pedido,
    PedidoDetalle,
    form=PedidoDetalleForm,  # <-- clave
    extra=1,
    can_delete=True,
)

class PatrimonioUnidadForm(forms.ModelForm):
    class Meta:
        model = PatrimonioUnidad
        fields = [
            "numero_patrimonio",
            "detalle_item",
            "nombre_pc",
            "ip",
            "usuario_asignado",
            "serial",
            "observaciones",
            "servicio_asignado",
        ]
        widgets = {
            "detalle_item":     forms.TextInput(attrs={"placeholder": "Ej: PC Dell OptiPlex 3000"}),
            "nombre_pc":        forms.TextInput(attrs={"placeholder": "Ej: HEEP-PC-042  (opcional)"}),
            "ip":               forms.TextInput(attrs={"placeholder": "Ej: 192.168.1.42  (opcional)"}),
            "usuario_asignado": forms.TextInput(attrs={"placeholder": "Nombre del usuario  (opcional)"}),
            "observaciones":    forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, pedido_detalle=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pedido_detalle = pedido_detalle
        self.user = user

        item = pedido_detalle.item if pedido_detalle else None
        self.es_impresora = bool(item and item.tipo == "IMPRESORA")
        self.es_articulo_patrimonial = bool(
            item and item.tipo == "ARTICULO" and item.articulo and item.articulo.es_patrimonial
        )
        self.genera_ficha = item.articulo.genera_ficha if (item and item.articulo) else ""

        # Al cargar el patrimonio de una impresora, precargamos los datos
        # que ya tiene el catálogo (marca/modelo/IP/nº patrimonio) para que
        # solo haya que personalizar lo que cambia por unidad.
        if self.es_impresora and self.instance.pk is None:
            impresora = item.impresora
            self.fields["detalle_item"].initial = f"{impresora.marca} {impresora.modelo}"
            if impresora.patrimonio:
                self.fields["numero_patrimonio"].initial = impresora.patrimonio
            if impresora.ip:
                self.fields["ip"].initial = impresora.ip
            if impresora.servicio_actual:
                self.fields["servicio_asignado"].initial = impresora.servicio_actual

        # Un artículo patrimonial es un catálogo (ej: "MiniPC"), no una unidad
        # física puntual: cada unidad cargada tiene su propio nº de patrimonio,
        # por eso acá solo precargamos el nombre y dejamos el número en blanco.
        elif self.es_articulo_patrimonial and self.instance.pk is None:
            self.fields["detalle_item"].initial = item.articulo.nombre

    def clean(self):
        cleaned = super().clean()
        if not self.pedido_detalle:
            return cleaned

        ya_cargados = self.pedido_detalle.patrimonios.count()

        # Si es creación (no edición), validar cupo
        if not self.instance.pk and ya_cargados >= self.pedido_detalle.cantidad:
            raise forms.ValidationError(
                f"Ya cargaste {ya_cargados}/{self.pedido_detalle.cantidad} patrimonios para este item."
            )

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.pedido_detalle = self.pedido_detalle
        obj.asignado_por = self.user
        if self.es_articulo_patrimonial:
            obj.articulo = self.pedido_detalle.item.articulo
        if commit:
            obj.save()
            if self.es_impresora:
                self._sync_impresora(obj)
            elif self.es_articulo_patrimonial:
                self._generar_ficha_desde_articulo(obj)
        return obj

    def _generar_ficha_desde_articulo(self, obj):
        generar_ficha_desde_articulo(obj, self.pedido_detalle.item.articulo)

    def _sync_impresora(self, obj):
        """
        La impresora es una unidad física real: lo que se carga acá (patrimonio,
        IP, servicio asignado) es el estado actual de ESA impresora, no una copia
        aparte. Por eso se escribe de vuelta sobre el registro de Impresora.
        """
        impresora = self.pedido_detalle.item.impresora

        campos = []
        if obj.numero_patrimonio and impresora.patrimonio != obj.numero_patrimonio:
            impresora.patrimonio = obj.numero_patrimonio
            campos.append("patrimonio")
        if obj.ip:
            try:
                validate_ipv46_address(obj.ip)
                if impresora.ip != obj.ip:
                    impresora.ip = obj.ip
                    campos.append("ip")
            except ValidationError:
                pass
        if campos:
            impresora.save(update_fields=campos)

        asignar_impresora_a_servicio(
            impresora,
            obj.servicio_asignado,
            responsable=obj.usuario_asignado or "",
        )
