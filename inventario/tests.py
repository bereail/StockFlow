from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from inventario.models import (
    Toner, Articulo, ActivoPC, Impresora, Servicio,
    Item, Movimiento, MovimientoDetalle,
    AsignacionImpresora, Nota, Pendiente, Reparacion,
    Prestamo, Pedido,
)
from inventario.services.stock import stock_de_item, hay_stock_suficiente
from inventario.services.items import (
    item_de_toner, item_de_articulo, item_de_pc, item_de_impresora,
)


# ============================================================
# STOCK SERVICE
# ============================================================

class StockServiceTest(TestCase):
    def setUp(self):
        self.servicio = Servicio.objects.create(nombre="Terapia")
        self.toner = Toner.objects.create(nombre="CE285A", marca="HP")
        self.item = item_de_toner(self.toner)

    def _mov(self, tipo, cantidad, anulado=False):
        mov = Movimiento.objects.create(tipo=tipo, servicio=self.servicio, anulado=anulado)
        MovimientoDetalle.objects.create(movimiento=mov, item=self.item, cantidad=cantidad)

    def test_stock_inicial_cero(self):
        self.assertEqual(stock_de_item(self.item.id), 0)

    def test_ingreso_suma(self):
        self._mov("INGRESO", 10)
        self.assertEqual(stock_de_item(self.item.id), 10)

    def test_egreso_resta(self):
        self._mov("INGRESO", 10)
        self._mov("EGRESO", 3)
        self.assertEqual(stock_de_item(self.item.id), 7)

    def test_ajuste_suma(self):
        self._mov("INGRESO", 10)
        self._mov("AJUSTE", 5)
        self.assertEqual(stock_de_item(self.item.id), 15)

    def test_ajuste_resta(self):
        self._mov("INGRESO", 10)
        self._mov("AJUSTE", -3)
        self.assertEqual(stock_de_item(self.item.id), 7)

    def test_movimiento_anulado_no_cuenta(self):
        self._mov("INGRESO", 10)
        self._mov("EGRESO", 3, anulado=True)
        self.assertEqual(stock_de_item(self.item.id), 10)

    def test_hay_stock_suficiente_ok(self):
        self._mov("INGRESO", 5)
        self.assertTrue(hay_stock_suficiente(self.item.id, 5))

    def test_hay_stock_suficiente_insuficiente(self):
        self._mov("INGRESO", 5)
        self.assertFalse(hay_stock_suficiente(self.item.id, 6))

    def test_hay_stock_suficiente_sin_stock(self):
        self.assertFalse(hay_stock_suficiente(self.item.id, 1))

    def test_multiplos_ingresos_y_egresos(self):
        self._mov("INGRESO", 20)
        self._mov("EGRESO", 5)
        self._mov("EGRESO", 3)
        self._mov("INGRESO", 10)
        self.assertEqual(stock_de_item(self.item.id), 22)


# ============================================================
# ITEM SERVICE
# ============================================================

class ItemServiceTest(TestCase):
    def test_item_de_toner_idempotente(self):
        toner = Toner.objects.create(nombre="TK-1110", marca="Kyocera")
        self.assertEqual(item_de_toner(toner).pk, item_de_toner(toner).pk)

    def test_item_de_toner_tipo_correcto(self):
        toner = Toner.objects.create(nombre="CE285A")
        self.assertEqual(item_de_toner(toner).tipo, "TONER")

    def test_item_de_articulo_idempotente(self):
        art = Articulo.objects.create(nombre="Cable USB")
        self.assertEqual(item_de_articulo(art).pk, item_de_articulo(art).pk)

    def test_item_de_articulo_tipo_correcto(self):
        art = Articulo.objects.create(nombre="Mouse")
        self.assertEqual(item_de_articulo(art).tipo, "ARTICULO")

    def test_item_de_pc_idempotente(self):
        pc = ActivoPC.objects.create(nombre_pc="PC-01")
        self.assertEqual(item_de_pc(pc).pk, item_de_pc(pc).pk)

    def test_item_de_pc_tipo_correcto(self):
        pc = ActivoPC.objects.create(nombre_pc="PC-02")
        self.assertEqual(item_de_pc(pc).tipo, "ACTIVO_PC")

    def test_item_de_impresora_idempotente(self):
        imp = Impresora.objects.create(marca="HP", modelo="1102", tipo="Laser", conexion="USB")
        self.assertEqual(item_de_impresora(imp).pk, item_de_impresora(imp).pk)

    def test_item_de_impresora_tipo_correcto(self):
        imp = Impresora.objects.create(marca="Canon", modelo="MF3010", tipo="Laser", conexion="USB")
        self.assertEqual(item_de_impresora(imp).tipo, "IMPRESORA")


# ============================================================
# MODELO: NOTA
# ============================================================

class NotaModelTest(TestCase):
    def setUp(self):
        self.servicio = Servicio.objects.create(nombre="Guardia")

    def test_fecha_cierre_se_setea_al_cerrar(self):
        nota = Nota.objects.create(servicio_solicitante=self.servicio, estado="BORRADOR")
        self.assertIsNone(nota.fecha_cierre)
        nota.estado = "CERRADA"
        nota.save()
        nota.refresh_from_db()
        self.assertIsNotNone(nota.fecha_cierre)

    def test_fecha_cierre_se_limpia_al_reabrir(self):
        nota = Nota.objects.create(servicio_solicitante=self.servicio, estado="CERRADA")
        nota.refresh_from_db()
        self.assertIsNotNone(nota.fecha_cierre)
        nota.estado = "BORRADOR"
        nota.save()
        nota.refresh_from_db()
        self.assertIsNone(nota.fecha_cierre)

    def test_str_con_numero_y_servicio(self):
        nota = Nota.objects.create(
            numero="001",
            servicio_solicitante=self.servicio,
            estado="BORRADOR",
        )
        self.assertIn("001", str(nota))
        self.assertIn("Guardia", str(nota))

    def test_str_sin_numero(self):
        nota = Nota.objects.create(servicio_solicitante=self.servicio, estado="BORRADOR")
        self.assertIn("Sin número", str(nota))


# ============================================================
# MODELO: ASIGNACION IMPRESORA (constraint unicidad)
# ============================================================

class AsignacionImpresoraTest(TestCase):
    def setUp(self):
        self.servicio1 = Servicio.objects.create(nombre="UCI")
        self.servicio2 = Servicio.objects.create(nombre="Guardia")
        self.imp = Impresora.objects.create(
            marca="HP", modelo="1102", tipo="Laser", conexion="USB"
        )

    def test_primera_asignacion_activa_ok(self):
        a = AsignacionImpresora.objects.create(impresora=self.imp, servicio=self.servicio1)
        self.assertIsNone(a.fecha_hasta)

    def test_dos_asignaciones_activas_falla(self):
        AsignacionImpresora.objects.create(impresora=self.imp, servicio=self.servicio1)
        with self.assertRaises(IntegrityError):
            AsignacionImpresora.objects.create(impresora=self.imp, servicio=self.servicio2)

    def test_dos_asignaciones_cerradas_ok(self):
        from django.utils import timezone
        hoy = timezone.localdate()
        AsignacionImpresora.objects.create(impresora=self.imp, servicio=self.servicio1, fecha_hasta=hoy)
        AsignacionImpresora.objects.create(impresora=self.imp, servicio=self.servicio2, fecha_hasta=hoy)
        self.assertEqual(self.imp.asignaciones.count(), 2)

    def test_propiedad_servicio_actual(self):
        AsignacionImpresora.objects.create(impresora=self.imp, servicio=self.servicio1)
        self.assertEqual(self.imp.servicio_actual, self.servicio1)

    def test_propiedad_servicio_actual_sin_asignacion(self):
        self.assertIsNone(self.imp.servicio_actual)


# ============================================================
# MODELO: PENDIENTE
# ============================================================

class PendienteModelTest(TestCase):
    def test_str(self):
        p = Pendiente.objects.create(texto="Revisar impresora")
        self.assertEqual(str(p), "Revisar impresora")

    def test_completado_default_false(self):
        p = Pendiente.objects.create(texto="Tarea")
        self.assertFalse(p.completado)

    def test_completar(self):
        p = Pendiente.objects.create(texto="Tarea")
        p.completado = True
        p.save(update_fields=["completado"])
        p.refresh_from_db()
        self.assertTrue(p.completado)


# ============================================================
# MODELO: IMPRESORA — validación IP
# ============================================================

class ImpresoraModelTest(TestCase):
    def test_conexion_ip_sin_ip_falla(self):
        from django.core.exceptions import ValidationError
        imp = Impresora(marca="HP", modelo="1102", tipo="Laser", conexion="IP", ip=None)
        with self.assertRaises(ValidationError):
            imp.clean()

    def test_conexion_usb_sin_ip_ok(self):
        imp = Impresora(marca="HP", modelo="1102", tipo="Laser", conexion="USB", ip=None)
        imp.clean()  # no debe lanzar


# ============================================================
# VISTAS — smoke tests
# ============================================================

class ViewsSmokeTest(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser("admin", "admin@test.com", "pw1234")
        self.client.force_login(self.user)

    def _get_ok(self, url):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200, f"GET {url} devolvió {r.status_code}")

    def test_dashboard(self):
        self._get_ok("/")

    def test_toner_page(self):
        self._get_ok("/toner/")

    def test_toner_list(self):
        self._get_ok("/toner/lista/")

    def test_toner_historial(self):
        self._get_ok("/toner/historial/")

    def test_toner_create_get(self):
        self._get_ok("/toner/nuevo/")

    def test_articulos_page(self):
        self._get_ok("/articulos/")

    def test_articulos_historial(self):
        self._get_ok("/articulos/historial/")

    def test_servicios_page(self):
        self._get_ok("/servicios/")

    def test_pcs_page(self):
        self._get_ok("/pcs/")

    def test_impresoras_page(self):
        self._get_ok("/impresoras/")

    def test_impresoras_historial(self):
        self._get_ok("/impresoras/historial/")

    def test_movimientos_list(self):
        self._get_ok("/movimientos/")

    def test_movimiento_create_get(self):
        self._get_ok("/movimientos/nuevo/")

    def test_prestamos_list(self):
        self._get_ok("/prestamos/")

    def test_pendientes_page(self):
        self._get_ok("/pendientes/")

    def test_reparaciones_list(self):
        self._get_ok("/reparaciones/")

    def test_pedidos_list(self):
        self._get_ok("/pedidos/")

    def test_notas_list(self):
        self._get_ok("/notas/")

    def test_nota_create_get(self):
        self._get_ok("/notas/nueva/")


# ============================================================
# VISTAS — operaciones de escritura
# ============================================================

class VistasCrudTest(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser("admin2", "admin2@test.com", "pw1234")
        self.client.force_login(self.user)
        self.servicio = Servicio.objects.create(nombre="Pediatría")

    def test_crear_toner(self):
        r = self.client.post("/toner/nuevo/", {"nombre": "CE285A", "marca": "HP", "activo": True})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Toner.objects.filter(nombre="CE285A").exists())

    def test_crear_servicio(self):
        r = self.client.post("/servicios/nuevo/", {"nombre": "Quirófano"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Servicio.objects.filter(nombre="Quirófano").exists())

    def test_crear_articulo(self):
        r = self.client.post("/articulos/nuevo/", {"nombre": "Teclado USB", "activo": True})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Articulo.objects.filter(nombre="Teclado USB").exists())

    def test_entrega_rapida_toner(self):
        from django.utils import timezone
        toner = Toner.objects.create(nombre="TK-1110", marca="Kyocera")
        r = self.client.post("/toner/entrega/", {
            "servicio": self.servicio.pk,
            "toner": toner.pk,
            "cantidad": 2,
            "fecha": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        })
        self.assertEqual(r.status_code, 302)
        item = item_de_toner(toner)
        self.assertEqual(stock_de_item(item.id), -2)

    def test_toggle_toner(self):
        toner = Toner.objects.create(nombre="CE255A", marca="HP", activo=True)
        self.client.post(f"/toner/{toner.pk}/toggle/")
        toner.refresh_from_db()
        self.assertFalse(toner.activo)

    def test_pendiente_toggle(self):
        p = Pendiente.objects.create(texto="Revisar switch", servicio=self.servicio)
        self.client.post(f"/pendientes/{p.pk}/toggle/")
        p.refresh_from_db()
        self.assertTrue(p.completado)

    def test_pendiente_delete(self):
        p = Pendiente.objects.create(texto="Borrar esto", servicio=self.servicio)
        self.client.post(f"/pendientes/{p.pk}/delete/")
        self.assertFalse(Pendiente.objects.filter(pk=p.pk).exists())


# ============================================================
# LOGIN — redirección sin autenticación
# ============================================================

class LoginRedirectTest(TestCase):
    def test_dashboard_sin_login_redirige(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r["Location"])

    def test_toner_sin_login_redirige(self):
        r = self.client.get("/toner/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r["Location"])
