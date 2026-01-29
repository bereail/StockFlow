# inventario/forms/__init__.py

# Toner
from .toner import TonerForm, EntregaRapidaTonerForm

# Artículos
from .articulos import ArticuloForm, EntregaRapidaArticuloForm

# Servicios / PCs (si los tenés)
from .servicios import ServicioForm
from .pcs import ActivoPCForm

# Impresoras
from .impresoras import ImpresoraForm, EntregaRapidaImpresoraForm

# Pendientes
from .pendientes import PendienteForm

# Reparaciones
from .reparaciones import ReparacionForm

# pedidos
from .pedidos import Pedido, PedidoDetalle, PedidoDetalleFormSet

#prestamos
from .prestamos import PrestamoForm

from .movimientos import (
    DocumentoForm,
    MovimientoForm,
    MovimientoDetalleTonerForm,
    MovimientoDetalleArticuloForm,
)
