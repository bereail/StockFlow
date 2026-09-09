"""
Carga un set de datos 100% ficticios que muestra todos los módulos de la
app en uso: stock con historial, préstamos activos y vencidos, pedidos en
distintos estados, patrimonios, notas, pendientes, reparaciones e
intercambios. Pensado para explorar la app localmente o levantar una demo,
no para instalaciones reales.

No pisa nada: si ya existen pedidos, asume que la demo ya se cargó (o que
es una base de datos real) y no hace nada.
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from inventario.models import (
    ActivoPC,
    Articulo,
    Impresora,
    Intercambio,
    Movimiento,
    MovimientoDetalle,
    Nota,
    NotaDetalle,
    PatrimonioUnidad,
    Pedido,
    PedidoDetalle,
    Pendiente,
    Prestamo,
    PrestamoDetalle,
    Proveedor,
    Reparacion,
    Servicio,
    Toner,
)
from inventario.services.impresoras import asignar_impresora_a_servicio
from inventario.services.items import (
    item_de_articulo,
    item_de_impresora,
    item_de_pc,
    item_de_toner,
)

random.seed(42)

SERVICIOS = [
    "Dirección", "Administración", "Recepción", "Recursos Humanos",
    "Farmacia", "Laboratorio", "Terapia Intensiva", "Guardia",
    "Quirófano", "Enfermería", "Radiología", "Mantenimiento",
]

TONERS = [
    ("HP 85A", "HP", "LaserJet P1102"),
    ("HP 78A", "HP", "LaserJet Pro M126"),
    ("Brother TN-660", "Brother", "HL-L2340DW"),
    ("Brother TN-1060", "Brother", "HL-1212W"),
    ("Samsung MLT-D111S", "Samsung", "SL-M2020"),
    ("Canon 137", "Canon", "imageCLASS MF212w"),
    ("Kyocera TK-1170", "Kyocera", "Ecosys M2040dn"),
    ("Epson 664", "Epson", "L3150"),
]

# nombre, marca, es_patrimonial, genera_ficha
ARTICULOS = [
    ("Mouse óptico USB", "Logitech", False, ""),
    ("Teclado USB", "Logitech", False, ""),
    ("Cable de red Cat6 (por metro)", "Nexxt", False, ""),
    ("Memoria RAM DDR4 8GB", "Kingston", False, ""),
    ("Disco SSD 480GB", "Kingston", False, ""),
    ("UPS 850VA", "APC", True, ""),
    ("Router", "TP-Link Archer C6", True, ""),
    ("Switch 24 puertos", "Aruba", True, ""),
    ("Monitor LED 21\"", "Samsung", True, ""),
    ("Notebook", "Dell Latitude 3420", True, "ACTIVO_PC"),
    ("PC de escritorio", "Lenovo ThinkCentre M70s", True, "ACTIVO_PC"),
    ("Impresora", "Brother HL-1212", True, "IMPRESORA"),
    ("Webcam", "Logitech C920", False, ""),
    ("Proyector", "Epson X39", True, ""),
]

PROVEEDORES = [
    ("InfoSur Insumos SRL", "0351-455-1122", "ventas@infosur.example.com"),
    ("TecnoService Córdoba", "0351-460-3344", "soporte@tecnoservice.example.com"),
    ("Distribuidora Central", "0351-470-5566", "pedidos@distcentral.example.com"),
]

NOMBRES = [
    "Marcos Ibáñez", "Lucía Fernández", "Gustavo Paz", "Romina Álvarez",
    "Sebastián Torres", "Carla Gómez", "Nicolás Ledesma", "Agustina Molina",
    "Diego Rearte", "Vanina Sosa",
]


def _fecha(dias_atras):
    return timezone.now() - timedelta(days=dias_atras)


class Command(BaseCommand):
    help = "Carga datos ficticios en todos los módulos para explorar la app o armar una demo."

    @transaction.atomic
    def handle(self, *args, **options):
        if Pedido.objects.exists():
            self.stdout.write(self.style.WARNING(
                "Seed demo: ya hay pedidos cargados, no se toca nada "
                "(evita duplicar datos en una base real)."
            ))
            return

        user = self._demo_user()

        servicios = self._servicios()
        toners = self._toners()
        articulos = self._articulos()
        proveedores = self._proveedores()

        pcs = self._activos_pc(servicios, articulos)
        impresoras = self._impresoras(servicios, articulos, toners)

        items_toner = {t.id: item_de_toner(t) for t in toners}
        items_articulo = {a.id: item_de_articulo(a) for a in articulos}
        items_pc = {pc.id: item_de_pc(pc) for pc in pcs}
        items_impresora = {i.id: item_de_impresora(i) for i in impresoras}

        self._movimientos(servicios, items_toner, items_articulo)
        self._prestamos(servicios, items_pc, items_articulo)
        self._reparaciones(servicios, proveedores, items_impresora, items_pc)
        pedidos = self._pedidos(servicios, proveedores, articulos, items_articulo, user)
        notas = self._notas(servicios, items_articulo)
        self._pendientes(servicios, pedidos, notas)
        self._intercambios(servicios, user)

        self.stdout.write(self.style.SUCCESS("Seed demo: datos ficticios cargados en todos los módulos."))

    # ------------------------------------------------------------------

    def _demo_user(self):
        User = get_user_model()
        user = User.objects.filter(is_superuser=True).order_by("id").first()
        if user:
            return user
        user = User.objects.create_superuser(
            username="demo", email="demo@example.com", password="demo1234",
        )
        self.stdout.write(self.style.SUCCESS(
            "Seed demo: no había ningún superusuario, se creó 'demo' / 'demo1234' (solo para uso local)."
        ))
        return user

    def _servicios(self):
        return [Servicio.objects.get_or_create(nombre=n)[0] for n in SERVICIOS]

    def _toners(self):
        return [
            Toner.objects.get_or_create(
                nombre=nombre, marca=marca, defaults={"modelo_impresora": modelo}
            )[0]
            for nombre, marca, modelo in TONERS
        ]

    def _articulos(self):
        articulos = []
        for nombre, marca, patrimonial, genera_ficha in ARTICULOS:
            art, _ = Articulo.objects.get_or_create(
                nombre=nombre,
                marca=marca,
                defaults={
                    "es_patrimonial": patrimonial,
                    "genera_ficha": genera_ficha,
                    "descripcion": f"{nombre} {marca}".strip(),
                },
            )
            articulos.append(art)
        return articulos

    def _proveedores(self):
        return [
            Proveedor.objects.get_or_create(
                nombre=nombre, defaults={"telefono": tel, "email": mail}
            )[0]
            for nombre, tel, mail in PROVEEDORES
        ]

    def _activos_pc(self, servicios, articulos):
        art_pc = next(a for a in articulos if a.nombre == "PC de escritorio")
        pcs = []
        for i in range(1, 9):
            servicio = random.choice(servicios)
            pc = ActivoPC.objects.create(
                articulo=art_pc,
                nombre_pc=f"PC-{servicio.nombre[:3].upper()}-{i:02d}",
                ip=f"192.168.1.{20 + i}",
                patrimonio=f"PAT-{1000 + i}",
                serie=f"SN-{random.randint(100000, 999999)}",
                servicio=servicio,
                observaciones="Equipo de uso general.",
            )
            pcs.append(pc)
        return pcs

    def _impresoras(self, servicios, articulos, toners):
        art_impresora = next(a for a in articulos if a.nombre == "Impresora")
        modelos = [
            ("Brother", "HL-1212W", "IP"), ("Brother", "HL-L2340DW", "IP"),
            ("HP", "LaserJet P1102", "USB"), ("HP", "LaserJet Pro M126", "IP"),
            ("Samsung", "SL-M2020", "USB"), ("Kyocera", "Ecosys M2040dn", "IP"),
        ]
        impresoras = []
        for idx, (marca, modelo, conexion) in enumerate(modelos, start=1):
            toner = next((t for t in toners if t.marca == marca), toners[0])
            impresora = Impresora.objects.create(
                articulo=art_impresora,
                marca=marca,
                modelo=modelo,
                tipo="Láser",
                patrimonio=f"PAT-{2000 + idx}",
                conexion=conexion,
                ip=f"192.168.1.{100 + idx}" if conexion == "IP" else None,
                toner=toner,
                estado="ACTIVA",
            )
            servicio = servicios[idx % len(servicios)]
            asignar_impresora_a_servicio(
                impresora, servicio,
                fecha=_fecha(90).date(),
                responsable=random.choice(NOMBRES),
                ubicacion="Planta baja" if idx % 2 == 0 else "Primer piso",
            )
            # Un par de impresoras se movieron de servicio (para mostrar historial).
            if idx <= 2:
                otro_servicio = servicios[(idx + 3) % len(servicios)]
                asignar_impresora_a_servicio(
                    impresora, otro_servicio,
                    fecha=_fecha(20).date(),
                    responsable=random.choice(NOMBRES),
                )
            impresoras.append(impresora)
        return impresoras

    def _movimientos(self, servicios, items_toner, items_articulo):
        items_toner_list = list(items_toner.values())
        items_articulo_list = list(items_articulo.values())

        # Ingresos de stock (últimos 4 meses).
        for semanas_atras in range(16, 0, -2):
            mov = Movimiento.objects.create(
                tipo="INGRESO", fecha=_fecha(semanas_atras * 7),
                observaciones="Ingreso por compra a proveedor.",
            )
            for item in random.sample(items_toner_list, k=3):
                MovimientoDetalle.objects.create(movimiento=mov, item=item, cantidad=random.randint(5, 15))

        # Entregas (egresos) a servicios, incluyendo el mes actual para el dashboard.
        for dias_atras in [3, 8, 15, 22, 35, 50, 65, 80]:
            mov = Movimiento.objects.create(
                tipo="EGRESO", fecha=_fecha(dias_atras),
                servicio=random.choice(servicios),
                observaciones="Entrega de insumos.",
            )
            for item in random.sample(items_toner_list, k=2):
                MovimientoDetalle.objects.create(movimiento=mov, item=item, cantidad=random.randint(1, 3))

        for dias_atras in [5, 18, 40, 60]:
            mov = Movimiento.objects.create(
                tipo="EGRESO", fecha=_fecha(dias_atras),
                servicio=random.choice(servicios),
                observaciones="Entrega de artículos varios.",
            )
            for item in random.sample(items_articulo_list, k=2):
                MovimientoDetalle.objects.create(movimiento=mov, item=item, cantidad=random.randint(1, 4))

    def _prestamos(self, servicios, items_pc, items_articulo):
        items_prestables = list(items_pc.values()) + [
            it for it in items_articulo.values()
            if it.articulo and it.articulo.nombre in ("Webcam", "Proyector", "Notebook")
        ]
        if not items_prestables:
            items_prestables = list(items_pc.values())

        casos = [
            # (días desde retiro, días de plazo, devuelto)
            (2, 7, False),
            (10, 5, False),   # vencido, sin devolver
            (20, 10, True),
            (35, 15, True),
            (60, 20, True),
        ]
        for dias_retiro, plazo, devuelto in casos:
            prestamo = Prestamo.objects.create(
                servicio=random.choice(servicios),
                telefono_contacto=f"351-{random.randint(4000000, 4999999)}",
                entregado_a=random.choice(NOMBRES),
                fecha_retiro=_fecha(dias_retiro),
                fecha_devolucion_estimada=(_fecha(dias_retiro) + timedelta(days=plazo)).date(),
                fecha_devolucion_real=_fecha(dias_retiro - plazo) if devuelto else None,
                observaciones="Préstamo para reunión." if plazo <= 10 else "",
            )
            PrestamoDetalle.objects.create(
                prestamo=prestamo, item=random.choice(items_prestables), cantidad=1,
            )

    def _reparaciones(self, servicios, proveedores, items_impresora, items_pc):
        estados = ["RECIBIDO", "ENVIADO", "EN_REPARACION", "LISTO", "RETIRADO", "CERRADO"]
        items = list(items_impresora.values()) + list(items_pc.values())
        for i, estado in enumerate(estados):
            Reparacion.objects.create(
                item=random.choice(items),
                proveedor=random.choice(proveedores),
                servicio=random.choice(servicios),
                estado=estado,
                fecha_envio=_fecha(30 - i * 3).date(),
                fecha_retorno=_fecha(10 - i * 3).date() if estado in ("LISTO", "RETIRADO", "CERRADO") else None,
                diagnostico=random.choice([
                    "No enciende.", "Atasco de papel recurrente.", "Falla de fusor.",
                    "No conecta a la red.", "Ruido anormal.", "Sin diagnóstico aún.",
                ]),
            )

    def _pedidos(self, servicios, proveedores, articulos, items_articulo, user):
        estados = ["HECHO", "APROBADO", "RECIBIDO", "ENTREGADO", "CANCELADO"]
        articulos_patrimoniales = [a for a in articulos if a.es_patrimonial]
        pedidos = []
        for i, estado in enumerate(estados, start=1):
            pedido = Pedido.objects.create(
                numero=f"PED-2026-{i:03d}",
                observaciones="Pedido de reposición de stock.",
                para_que=random.choice(["Reposición general", "Equipamiento nuevo puesto", "Reemplazo por rotura"]),
                proveedor=random.choice(proveedores),
                estado=estado,
                fecha_aprobado=_fecha(50 - i * 5).date() if estado != "HECHO" else None,
                fecha_recibido=_fecha(30 - i * 5).date() if estado in ("RECIBIDO", "ENTREGADO") else None,
                fecha_entregado=_fecha(15 - i * 2).date() if estado == "ENTREGADO" else None,
            )
            pedido.servicios.set(random.sample(servicios, k=2))

            articulo = random.choice(articulos)
            detalle = PedidoDetalle.objects.create(
                pedido=pedido, item=items_articulo[articulo.id], cantidad=random.randint(1, 5),
                detalle=f"{articulo.nombre} {articulo.marca}",
            )

            # Los pedidos ya recibidos generan su patrimonio (y su ficha, si corresponde).
            if estado in ("RECIBIDO", "ENTREGADO") and articulo in articulos_patrimoniales:
                unidad = PatrimonioUnidad.objects.create(
                    articulo=articulo,
                    pedido_detalle=detalle,
                    numero_patrimonio=f"PAT-{3000 + i}",
                    detalle_item=f"{articulo.nombre} {articulo.marca}",
                    servicio_asignado=pedido.servicios.first(),
                    asignado_por=user,
                )
                from inventario.services.patrimonios import generar_ficha_desde_articulo
                generar_ficha_desde_articulo(unidad, articulo)

            pedidos.append(pedido)
        return pedidos

    def _notas(self, servicios, items_articulo):
        estados = ["BORRADOR", "ENVIADA", "RECIBIDA", "ENTREGADA_MESA_ENTRADA", "FINALIZADA"]
        notas = []
        for i, estado in enumerate(estados, start=1):
            nota = Nota.objects.create(
                numero=f"NOTA-2026-{i:03d}",
                servicio_solicitante=random.choice(servicios),
                fecha=_fecha(40 - i * 5).date(),
                detalle="Solicitud de insumos varios para el sector.",
                estado=estado,
            )
            item = random.choice(list(items_articulo.values()))
            NotaDetalle.objects.create(nota=nota, item=item, cantidad=random.randint(1, 3))
            notas.append(nota)
        return notas

    def _pendientes(self, servicios, pedidos, notas):
        estados = ["PENDIENTE", "EN_PROGRESO", "COMPLETADO", "CANCELADO"]
        textos = [
            "Confirmar recepción con el proveedor",
            "Coordinar entrega con el sector",
            "Revisar stock antes de aprobar",
            "Hacer seguimiento del envío a reparación",
            "Actualizar planilla de patrimonio",
            "Contactar a mesa de entrada",
        ]
        for i, texto in enumerate(textos):
            Pendiente.objects.create(
                texto=texto,
                estado=estados[i % len(estados)],
                fecha_limite=_fecha(-5 - i * 3).date(),  # a futuro
                servicio=random.choice(servicios),
                pedido=random.choice(pedidos) if i % 3 == 0 else None,
                nota=random.choice(notas) if i % 3 == 1 else None,
            )

    def _intercambios(self, servicios, user):
        estados = ["PENDIENTE", "RESUELTO", "CANCELADO"]
        for i, estado in enumerate(estados):
            a, b = random.sample(servicios, k=2)
            Intercambio.objects.create(
                servicio_afectado=a,
                servicio_beneficiario=b,
                detalle_saliente="Notebook Dell Latitude (préstamo urgente)",
                motivo="El equipo nuevo todavía no llegó del proveedor.",
                estado=estado,
                fecha_intercambio=_fecha(25 - i * 5),
                creado_por=user,
                detalle_entrante="Notebook Dell Latitude nueva" if estado == "RESUELTO" else "",
                fecha_resolucion=_fecha(5) if estado == "RESUELTO" else None,
                resuelto_por=user if estado == "RESUELTO" else None,
            )
