# Nota
from .nota import NotaForm, NotaDetalleForm, NotaDetalleFormSet

# Toner
from .toner import TonerForm, EntregaRapidaTonerForm

# Artículos
from .articulos import ArticuloForm, EntregaRapidaArticuloForm

# Servicios / PCs
from .servicios import ServicioForm
from .pcs import ActivoPCForm

# Impresoras
from .impresoras import ImpresoraForm, EntregaRapidaImpresoraForm

# Pendientes
from .pendientes import PendienteForm

# Reparaciones
from .reparaciones import ReparacionForm

# Pedidos (OJO: acá solo forms/formsets, no modelos)
from .pedidos import PedidoForm, PedidoDetalleFormSet  # ajustá a tus nombres reales

# Préstamos
from .prestamos import PrestamoForm

# Movimientos
from .movimientos import (
    DocumentoForm,
    MovimientoForm,
    MovimientoDetalleTonerForm,
    MovimientoDetalleArticuloForm,
)

# Asignaciones
from .asignaciones import AsignacionImpresoraForm