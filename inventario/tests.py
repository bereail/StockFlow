import os
import tempfile
import threading
from unittest.mock import patch

from django.core.management import call_command
from django.db import connections, transaction
from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from inventario.models import (
    Toner, Articulo, ActivoPC, Impresora, Servicio, ItemComponente,
    Movimiento, MovimientoDetalle,
    AsignacionImpresora, Nota, Pendiente, Reparacion,
    Prestamo, PrestamoDetalle, Pedido, PedidoDetalle, PatrimonioUnidad, Intercambio,
)
from inventario.services.servicios import historial_de_servicio
from inventario.services.listados import ordenar
from inventario.services.stock import (
    stock_de_item, verificar_stock_suficiente, toners_con_stock_critico,
    lock_item_para_egreso, stock_armable_de_combo, crear_detalle_egreso,
)
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

    def test_verificar_stock_suficiente_ok_no_lanza(self):
        self._mov("INGRESO", 5)
        verificar_stock_suficiente(self.item, 5)  # no debe lanzar

    def test_verificar_stock_suficiente_insuficiente_lanza(self):
        self._mov("INGRESO", 5)
        with self.assertRaises(ValidationError):
            verificar_stock_suficiente(self.item, 6)

    def test_stock_critico_sin_minimo_configurado_no_alerta(self):
        self._mov("INGRESO", 1)
        self.assertEqual(toners_con_stock_critico(), [])

    def test_stock_critico_por_debajo_del_minimo_alerta(self):
        self.toner.stock_minimo = 5
        self.toner.save(update_fields=["stock_minimo"])
        self._mov("INGRESO", 3)
        criticos = toners_con_stock_critico()
        self.assertEqual(len(criticos), 1)
        self.assertEqual(criticos[0]["toner"], self.toner)
        self.assertEqual(criticos[0]["stock"], 3)

    def test_stock_por_encima_del_minimo_no_alerta(self):
        self.toner.stock_minimo = 5
        self.toner.save(update_fields=["stock_minimo"])
        self._mov("INGRESO", 10)
        self.assertEqual(toners_con_stock_critico(), [])

    def test_multiplos_ingresos_y_egresos(self):
        self._mov("INGRESO", 20)
        self._mov("EGRESO", 5)
        self._mov("EGRESO", 3)
        self._mov("INGRESO", 10)
        self.assertEqual(stock_de_item(self.item.id), 22)


# ============================================================
# STOCK — CONCURRENCIA (TEST-03 / STK-02)
# ============================================================

class StockConcurrenciaTest(TransactionTestCase):
    """
    Dos egresos concurrentes del mismo item, con stock para uno solo, no
    deben poder sobregirar el stock (ver STK-02 en la auditoría de
    2026-10-23: antes de `lock_item_para_egreso()`, dos requests podían leer
    "hay stock suficiente" cada uno por separado antes de que cualquiera
    llegara a escribir).

    Corre contra un archivo sqlite temporal real en vez del `:memory:` que
    usa el resto de la suite: con sqlite en memoria, cada conexión (cada
    thread tiene la suya) ve una base completamente separada y vacía, así
    que la concurrencia real nunca se pondría a prueba. Se restaura la base
    en memoria original al terminar — ningún otro test depende de datos
    creados por este, cada uno arma los propios.
    """
    databases = {"default"}

    @classmethod
    def setUpClass(cls):
        fd, cls._tmp_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        cls._orig_name = connections["default"].settings_dict["NAME"]
        cls.addClassCleanup(cls._restaurar_db_en_memoria)
        connections["default"].settings_dict["NAME"] = cls._tmp_path
        connections["default"].close()
        call_command("migrate", run_syncdb=True, verbosity=0)
        super().setUpClass()

    @classmethod
    def _restaurar_db_en_memoria(cls):
        connections["default"].close()
        connections["default"].settings_dict["NAME"] = cls._orig_name
        connections["default"].close()
        call_command("migrate", run_syncdb=True, verbosity=0)
        try:
            os.remove(cls._tmp_path)
        except OSError:
            pass

    def test_dos_egresos_concurrentes_no_sobregiran_stock(self):
        servicio = Servicio.objects.create(nombre="Guardia")
        toner = Toner.objects.create(nombre="Test concurrencia", marca="X")
        item = item_de_toner(toner)
        ingreso = Movimiento.objects.create(tipo="INGRESO")
        MovimientoDetalle.objects.create(movimiento=ingreso, item=item, cantidad=5)

        resultados = []

        def egresar():
            try:
                with transaction.atomic():
                    lock_item_para_egreso(item)
                    verificar_stock_suficiente(item, 5)
                    mov = Movimiento.objects.create(tipo="EGRESO", servicio=servicio)
                    MovimientoDetalle.objects.create(movimiento=mov, item=item, cantidad=5)
                resultados.append("ok")
            except ValidationError:
                resultados.append("rechazado")
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=egresar) for _ in range(2)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()

        self.assertEqual(sorted(resultados), ["ok", "rechazado"])
        self.assertEqual(stock_de_item(item.pk), 0)


# ============================================================
# STOCK — COMBOS (STK-04)
# ============================================================

class StockComboTest(TestCase):
    def setUp(self):
        self.servicio = Servicio.objects.create(nombre="Terapia")

        self.combo_articulo = Articulo.objects.create(nombre="Kit de instalación")
        self.combo_item = item_de_articulo(self.combo_articulo)
        self.combo_item.es_combo = True
        self.combo_item.save(update_fields=["es_combo"])

        self.toner = Toner.objects.create(nombre="CE285A", marca="HP")
        self.toner_item = item_de_toner(self.toner)

        self.cable = Articulo.objects.create(nombre="Cable de red")
        self.cable_item = item_de_articulo(self.cable)

        ItemComponente.objects.create(item_padre=self.combo_item, item_hijo=self.toner_item, cantidad=1)
        ItemComponente.objects.create(item_padre=self.combo_item, item_hijo=self.cable_item, cantidad=2)

    def _ingreso(self, item, cantidad):
        mov = Movimiento.objects.create(tipo="INGRESO")
        MovimientoDetalle.objects.create(movimiento=mov, item=item, cantidad=cantidad)

    def test_combo_sin_componentes_no_se_puede_armar(self):
        item = item_de_articulo(Articulo.objects.create(nombre="Combo vacío"))
        item.es_combo = True
        item.save(update_fields=["es_combo"])
        self.assertEqual(stock_armable_de_combo(item), 0)

    def test_armable_es_el_minimo_entre_componentes(self):
        self._ingreso(self.toner_item, 5)
        self._ingreso(self.cable_item, 6)  # alcanza para 3 combos (6 // 2)
        self.assertEqual(stock_armable_de_combo(self.combo_item), 3)

    def test_armable_nunca_negativo_aunque_un_componente_tenga_stock_negativo(self):
        self._ingreso(self.toner_item, 5)
        self._ingreso(self.cable_item, 1)
        MovimientoDetalle.objects.create(
            movimiento=Movimiento.objects.create(tipo="EGRESO"), item=self.cable_item, cantidad=5,
        )  # cable queda en -4, dato histórico, no se "corrige"
        self.assertEqual(stock_armable_de_combo(self.combo_item), 0)

    def test_verificar_stock_combo_ok_no_lanza(self):
        self._ingreso(self.toner_item, 5)
        self._ingreso(self.cable_item, 10)
        verificar_stock_suficiente(self.combo_item, 3)  # no debe lanzar

    def test_verificar_stock_combo_insuficiente_lanza(self):
        self._ingreso(self.toner_item, 1)
        self._ingreso(self.cable_item, 10)
        with self.assertRaises(ValidationError):
            verificar_stock_suficiente(self.combo_item, 2)  # solo hay 1 toner

    def test_verificar_stock_combo_sin_componentes_lanza(self):
        item = item_de_articulo(Articulo.objects.create(nombre="Combo vacío 2"))
        item.es_combo = True
        item.save(update_fields=["es_combo"])
        with self.assertRaises(ValidationError):
            verificar_stock_suficiente(item, 1)

    def test_egreso_de_combo_descuenta_cada_componente(self):
        self._ingreso(self.toner_item, 5)
        self._ingreso(self.cable_item, 10)

        mov = Movimiento.objects.create(tipo="EGRESO", servicio=self.servicio)
        crear_detalle_egreso(mov, self.combo_item, 2)

        self.assertEqual(stock_de_item(self.toner_item.pk), 3)   # 5 - 2*1
        self.assertEqual(stock_de_item(self.cable_item.pk), 6)   # 10 - 2*2
        # El combo en sí también queda registrado en su propio historial.
        self.assertEqual(
            MovimientoDetalle.objects.filter(movimiento=mov, item=self.combo_item).count(), 1
        )

    def test_anular_movimiento_de_combo_restaura_stock_de_componentes(self):
        self._ingreso(self.toner_item, 5)
        self._ingreso(self.cable_item, 10)

        mov = Movimiento.objects.create(tipo="EGRESO", servicio=self.servicio)
        crear_detalle_egreso(mov, self.combo_item, 2)
        mov.anulado = True
        mov.save(update_fields=["anulado"])

        self.assertEqual(stock_de_item(self.toner_item.pk), 5)
        self.assertEqual(stock_de_item(self.cable_item.pk), 10)

    def test_item_sin_combo_no_se_ve_afectado_por_logica_de_combo(self):
        self._ingreso(self.toner_item, 5)
        mov = Movimiento.objects.create(tipo="EGRESO", servicio=self.servicio)
        crear_detalle_egreso(mov, self.toner_item, 2)
        self.assertEqual(stock_de_item(self.toner_item.pk), 3)
        self.assertEqual(MovimientoDetalle.objects.filter(movimiento=mov).count(), 1)


class StockComboEntregaViewTest(TestCase):
    """Prueba de verificación de STK-04 de punta a punta: entregar un combo
    desde la vista real descuenta el stock de cada componente."""

    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser("admin", "admin@test.com", "pw1234")
        self.client.force_login(self.user)

        self.servicio = Servicio.objects.create(nombre="Terapia")
        self.combo_articulo = Articulo.objects.create(nombre="Kit de instalación")
        combo_item = item_de_articulo(self.combo_articulo)
        combo_item.es_combo = True
        combo_item.save(update_fields=["es_combo"])

        self.toner = Toner.objects.create(nombre="CE285A", marca="HP")
        toner_item = item_de_toner(self.toner)
        mov = Movimiento.objects.create(tipo="INGRESO")
        MovimientoDetalle.objects.create(movimiento=mov, item=toner_item, cantidad=5)

        ItemComponente.objects.create(item_padre=combo_item, item_hijo=toner_item, cantidad=1)
        self.toner_item = toner_item

    def test_entrega_de_combo_via_vista_descuenta_componente(self):
        r = self.client.post("/articulos/entrega/", {
            "servicio": self.servicio.pk,
            "articulo": self.combo_articulo.pk,
            "cantidad": 2,
        })
        self.assertRedirects(r, "/articulos/")
        self.assertEqual(stock_de_item(self.toner_item.pk), 3)


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
        nota.estado = "FINALIZADA"
        nota.save()
        nota.refresh_from_db()
        self.assertIsNotNone(nota.fecha_cierre)

    def test_fecha_cierre_se_limpia_al_reabrir(self):
        nota = Nota.objects.create(servicio_solicitante=self.servicio, estado="FINALIZADA")
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

    def test_estado_default_pendiente(self):
        p = Pendiente.objects.create(texto="Tarea")
        self.assertEqual(p.estado, "PENDIENTE")

    def test_completar(self):
        p = Pendiente.objects.create(texto="Tarea")
        p.estado = "COMPLETADO"
        p.save(update_fields=["estado"])
        p.refresh_from_db()
        self.assertEqual(p.estado, "COMPLETADO")


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

    def test_ip_duplicada_falla(self):
        Impresora.objects.create(marca="HP", modelo="1102", tipo="Laser", conexion="IP", ip="192.168.1.50")
        dup = Impresora(marca="Brother", modelo="HL-1212", tipo="Laser", conexion="IP", ip="192.168.1.50")
        with self.assertRaises(ValidationError):
            dup.clean()

    def test_dos_impresoras_sin_ip_no_chocan(self):
        Impresora.objects.create(marca="HP", modelo="1102", tipo="Laser", conexion="USB", ip=None)
        otra = Impresora(marca="Brother", modelo="HL-1212", tipo="Laser", conexion="USB", ip=None)
        otra.clean()  # no debe lanzar: NULL no cuenta como duplicado

    def test_patrimonio_duplicado_falla(self):
        Impresora.objects.create(marca="HP", modelo="1102", tipo="Laser", conexion="USB", patrimonio="12345")
        dup = Impresora(marca="Brother", modelo="HL-1212", tipo="Laser", conexion="USB", patrimonio="12345")
        with self.assertRaises(ValidationError):
            dup.clean()

    def test_dos_impresoras_sin_patrimonio_no_chocan(self):
        Impresora.objects.create(marca="HP", modelo="1102", tipo="Laser", conexion="USB", patrimonio="")
        otra = Impresora(marca="Brother", modelo="HL-1212", tipo="Laser", conexion="USB", patrimonio="")
        otra.clean()  # no debe lanzar: patrimonio vacío no cuenta como duplicado


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

    def test_dashboard_muestra_alerta_de_stock_critico(self):
        servicio = Servicio.objects.create(nombre="Terapia")
        toner = Toner.objects.create(nombre="CE285A", marca="HP", stock_minimo=5)
        item = item_de_toner(toner)
        mov = Movimiento.objects.create(tipo="INGRESO", servicio=servicio)
        MovimientoDetalle.objects.create(movimiento=mov, item=item, cantidad=2)

        r = self.client.get("/")
        self.assertContains(r, "Stock crítico de tóner")
        self.assertContains(r, "1 tipo")

    def test_toner_page(self):
        self._get_ok("/toner/")

    def test_toner_list(self):
        self._get_ok("/toner/lista/")

    def test_toner_historial(self):
        self._get_ok("/toner/historial/")

    def test_toner_create_get(self):
        r = self.client.get("/toner/nuevo/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Nuevo tóner")
        self.assertContains(r, 'name="nombre"')

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
        r = self.client.get("/movimientos/nuevo/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Nuevo Movimiento")
        self.assertContains(r, 'name="tipo"')
        self.assertContains(r, 'name="fecha"')

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

    def test_reportes_page(self):
        self._get_ok("/reportes/")

    def test_reporte_toner_html(self):
        servicio = Servicio.objects.create(nombre="Terapia")
        toner = Toner.objects.create(nombre="CE285A", marca="HP")
        item = item_de_toner(toner)
        mov = Movimiento.objects.create(tipo="EGRESO", servicio=servicio)
        MovimientoDetalle.objects.create(movimiento=mov, item=item, cantidad=3)

        r = self.client.get("/reportes/toner.html")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "CE285A")
        self.assertContains(r, "Subtotal — Terapia")
        self.assertContains(r, '<div class="sum-val">3</div>')

    def test_reporte_pcs_html(self):
        r = self.client.get("/reportes/pcs.html")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Equipos y patrimonios")
        self.assertContains(r, "Sin patrimonios registrados.")

    def test_reporte_pedidos_html(self):
        self._get_ok("/reportes/pedidos.html")

    def test_reporte_movimientos_html(self):
        servicio = Servicio.objects.create(nombre="Guardia")
        toner = Toner.objects.create(nombre="CF283A", marca="HP")
        item = item_de_toner(toner)
        mov = Movimiento.objects.create(tipo="INGRESO", servicio=servicio, observaciones="Compra anual")
        MovimientoDetalle.objects.create(movimiento=mov, item=item, cantidad=10)

        r = self.client.get("/reportes/movimientos.html")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "CF283A")
        self.assertContains(r, "Guardia")
        self.assertContains(r, "Compra anual")
        self.assertContains(r, "Total: 1 movimientos")

    def test_pcs_reporte_csv(self):
        self._get_ok("/reportes/pcs.csv")

    def test_pedidos_reporte_csv(self):
        self._get_ok("/reportes/pedidos.csv")

    def test_reporte_movimientos_html_escapa_observaciones_maliciosas(self):
        payload = "<script>alert(1)</script>"
        servicio = Servicio.objects.create(nombre="Terapia")
        toner = Toner.objects.create(nombre="TK-1110", marca="Kyocera")
        item = item_de_toner(toner)
        mov = Movimiento.objects.create(tipo="EGRESO", servicio=servicio, observaciones=payload)
        MovimientoDetalle.objects.create(movimiento=mov, item=item, cantidad=1)

        r = self.client.get("/reportes/movimientos.html")
        contenido = r.content.decode("utf-8")
        self.assertNotIn(payload, contenido)
        self.assertIn("&lt;script&gt;", contenido)

    def test_reporte_toner_html_escapa_parametro_mes_reflejado(self):
        payload = '"><script>alert(1)</script>'
        r = self.client.get("/reportes/toner.html", {"mes": payload})
        contenido = r.content.decode("utf-8")
        self.assertNotIn("<script>alert(1)</script>", contenido)


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

    def test_eliminar_servicio_sin_asociaciones(self):
        servicio = Servicio.objects.create(nombre="Sin uso")
        r = self.client.post(f"/servicios/{servicio.pk}/eliminar/")
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Servicio.objects.filter(pk=servicio.pk).exists())

    def test_eliminar_servicio_con_asociaciones_se_bloquea(self):
        ActivoPC.objects.create(nombre_pc="PC-01", servicio=self.servicio)
        r = self.client.post(f"/servicios/{self.servicio.pk}/eliminar/", follow=True)
        self.assertTrue(Servicio.objects.filter(pk=self.servicio.pk).exists())
        self.assertContains(r, "No se puede eliminar")

    def test_eliminar_servicio_requiere_post(self):
        servicio = Servicio.objects.create(nombre="Sin uso")
        r = self.client.get(f"/servicios/{servicio.pk}/eliminar/")
        self.assertEqual(r.status_code, 405)

    def test_crear_articulo(self):
        r = self.client.post("/articulos/nuevo/", {"nombre": "Teclado USB", "activo": True})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Articulo.objects.filter(nombre="Teclado USB").exists())

    def test_entrega_rapida_toner_sin_stock_no_se_permite(self):
        from django.utils import timezone
        toner = Toner.objects.create(nombre="TK-1110", marca="Kyocera")
        r = self.client.post("/toner/entrega/", {
            "servicio": self.servicio.pk,
            "toner": toner.pk,
            "cantidad": 2,
            "fecha": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        })
        self.assertEqual(r.status_code, 200)  # re-renderiza el form con error, no redirige
        item = item_de_toner(toner)
        self.assertEqual(stock_de_item(item.id), 0)  # el stock no queda negativo

    def test_entrega_rapida_toner_con_stock_suficiente(self):
        from django.utils import timezone
        toner = Toner.objects.create(nombre="TK-1110", marca="Kyocera")
        item = item_de_toner(toner)
        mov = Movimiento.objects.create(tipo="INGRESO", servicio=self.servicio)
        MovimientoDetalle.objects.create(movimiento=mov, item=item, cantidad=5)

        r = self.client.post("/toner/entrega/", {
            "servicio": self.servicio.pk,
            "toner": toner.pk,
            "cantidad": 2,
            "fecha": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(stock_de_item(item.id), 3)

    def test_entrega_rapida_articulo_sin_stock_no_se_permite(self):
        from django.utils import timezone
        articulo = Articulo.objects.create(nombre="Mouse óptico")
        r = self.client.post("/articulos/entrega/", {
            "servicio": self.servicio.pk,
            "articulo": articulo.pk,
            "cantidad": 1,
            "fecha": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        })
        self.assertEqual(r.status_code, 200)
        item = item_de_articulo(articulo)
        self.assertEqual(stock_de_item(item.id), 0)

    def test_movimiento_create_egreso_sin_stock_no_se_permite(self):
        from django.utils import timezone
        toner = Toner.objects.create(nombre="TK-1110", marca="Kyocera")
        r = self.client.post("/movimientos/nuevo/", {
            "tipo": "EGRESO",
            "servicio": self.servicio.pk,
            "fecha": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "toner-TOTAL_FORMS": "1",
            "toner-INITIAL_FORMS": "0",
            "toner-MIN_NUM_FORMS": "0",
            "toner-MAX_NUM_FORMS": "1000",
            "toner-0-toner": str(toner.pk),
            "toner-0-cantidad": "3",
            "art-TOTAL_FORMS": "0",
            "art-INITIAL_FORMS": "0",
            "art-MIN_NUM_FORMS": "0",
            "art-MAX_NUM_FORMS": "1000",
        })
        self.assertEqual(r.status_code, 200)
        item = item_de_toner(toner)
        self.assertEqual(stock_de_item(item.id), 0)
        self.assertFalse(Movimiento.objects.filter(tipo="EGRESO").exists())

    def _crear_item_prestable(self, nombre="Proyector Epson"):
        articulo = Articulo.objects.create(nombre=nombre)
        item = item_de_articulo(articulo)
        item.prestable = True
        item.save(update_fields=["prestable"])
        return item

    def _formset_data(self, item_pk, extra=None):
        from django.utils import timezone
        data = {
            "servicio": self.servicio.pk,
            "entregado_a": "Juan Pérez",
            "fecha_retiro": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "detalles-TOTAL_FORMS": "1",
            "detalles-INITIAL_FORMS": "0",
            "detalles-MIN_NUM_FORMS": "0",
            "detalles-MAX_NUM_FORMS": "1000",
            "detalles-0-item": str(item_pk),
            "detalles-0-cantidad": "1",
        }
        if extra:
            data.update(extra)
        return data

    def test_prestamo_create_ok(self):
        item = self._crear_item_prestable()
        r = self.client.post("/mas/prestamos/nuevo/", self._formset_data(item.pk))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Prestamo.objects.filter(detalles__item=item).exists())

    def test_prestamo_no_permite_doble_reserva_del_mismo_item(self):
        item = self._crear_item_prestable()
        r1 = self.client.post("/mas/prestamos/nuevo/", self._formset_data(item.pk))
        self.assertEqual(r1.status_code, 302)

        r2 = self.client.post("/mas/prestamos/nuevo/", self._formset_data(item.pk))
        self.assertEqual(r2.status_code, 200)  # re-renderiza con error, no crea un segundo préstamo
        self.assertEqual(Prestamo.objects.filter(detalles__item=item).count(), 1)

    def test_prestamo_devuelto_libera_el_item_para_prestar_de_nuevo(self):
        item = self._crear_item_prestable()
        self.client.post("/mas/prestamos/nuevo/", self._formset_data(item.pk))
        prestamo1 = Prestamo.objects.get(detalles__item=item)

        self.client.post(f"/prestamos/{prestamo1.pk}/devolver/")
        prestamo1.refresh_from_db()
        self.assertTrue(prestamo1.devuelto)

        r2 = self.client.post("/mas/prestamos/nuevo/", self._formset_data(item.pk))
        self.assertEqual(r2.status_code, 302)
        self.assertEqual(Prestamo.objects.filter(detalles__item=item).count(), 2)

    def test_prestamo_edit_reeditar_sin_cambios_no_dispara_error_de_doble_reserva(self):
        item = self._crear_item_prestable()
        self.client.post("/mas/prestamos/nuevo/", self._formset_data(item.pk))
        prestamo = Prestamo.objects.get(detalles__item=item)
        detalle = prestamo.detalles.first()

        data = self._formset_data(item.pk, extra={
            "detalles-INITIAL_FORMS": "1",
            "detalles-0-id": str(detalle.pk),
        })
        r = self.client.post(f"/prestamos/{prestamo.pk}/editar/", data)
        self.assertEqual(r.status_code, 302)

    def test_toggle_toner(self):
        toner = Toner.objects.create(nombre="CE255A", marca="HP", activo=True)
        self.client.post(f"/toner/{toner.pk}/toggle/")
        toner.refresh_from_db()
        self.assertFalse(toner.activo)

    def test_movimiento_anular(self):
        toner = Toner.objects.create(nombre="TK-1110", marca="Kyocera")
        item = item_de_toner(toner)
        mov = Movimiento.objects.create(tipo="INGRESO", servicio=self.servicio)
        MovimientoDetalle.objects.create(movimiento=mov, item=item, cantidad=5)
        self.assertEqual(stock_de_item(item.id), 5)

        r = self.client.post(f"/movimientos/{mov.pk}/anular/")
        self.assertEqual(r.status_code, 302)
        mov.refresh_from_db()
        self.assertTrue(mov.anulado)
        self.assertEqual(stock_de_item(item.id), 0)

    def test_movimiento_anular_requiere_post(self):
        mov = Movimiento.objects.create(tipo="INGRESO", servicio=self.servicio)
        r = self.client.get(f"/movimientos/{mov.pk}/anular/")
        self.assertEqual(r.status_code, 405)

    def test_pendiente_toggle(self):
        p = Pendiente.objects.create(texto="Revisar switch", servicio=self.servicio)
        self.client.post(f"/pendientes/{p.pk}/toggle/")
        p.refresh_from_db()
        self.assertEqual(p.estado, "EN_PROGRESO")

    def test_pendiente_delete(self):
        p = Pendiente.objects.create(texto="Borrar esto", servicio=self.servicio)
        self.client.post(f"/pendientes/{p.pk}/delete/")
        self.assertFalse(Pendiente.objects.filter(pk=p.pk).exists())

    def test_pendiente_create_for_nota(self):
        nota = Nota.objects.create(numero="N-500", servicio_solicitante=self.servicio)
        r = self.client.post(f"/notas/{nota.pk}/pendientes/nuevo/", {
            "texto": "Revisar entrega",
            "servicio": self.servicio.pk,
        })
        self.assertEqual(r.status_code, 302)
        p = Pendiente.objects.get(texto="Revisar entrega")
        self.assertEqual(p.nota, nota)

    def test_pendiente_toggle_redirige_a_nota(self):
        nota = Nota.objects.create(numero="N-501", servicio_solicitante=self.servicio)
        p = Pendiente.objects.create(texto="Tarea de nota", nota=nota)
        r = self.client.post(f"/pendientes/{p.pk}/toggle/")
        self.assertRedirects(r, f"/notas/{nota.pk}/")


# ============================================================
# INTERCAMBIOS
# ============================================================

class IntercambioTest(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser("admin3", "admin3@test.com", "pw1234")
        self.client.force_login(self.user)
        self.enfermeria = Servicio.objects.create(nombre="Enfermería")
        self.guardia = Servicio.objects.create(nombre="Guardia")
        self.pat_saliente = PatrimonioUnidad.objects.create(
            numero_patrimonio="PAT-001", servicio_asignado=self.enfermeria, asignado_por=self.user,
        )
        self.pat_entrante = PatrimonioUnidad.objects.create(
            numero_patrimonio="PAT-002", servicio_asignado=self.guardia, asignado_por=self.user,
        )

    def test_crear_intercambio_actualiza_servicio_saliente(self):
        r = self.client.post("/intercambios/nuevo/", {
            "servicio_afectado": self.enfermeria.pk,
            "servicio_beneficiario": self.guardia.pk,
            "patrimonio_saliente": self.pat_saliente.pk,
            "fecha_intercambio": "2026-01-01T10:00",
        })
        self.assertEqual(r.status_code, 302)
        intercambio = Intercambio.objects.get()
        self.assertEqual(intercambio.estado, "PENDIENTE")
        self.pat_saliente.refresh_from_db()
        self.assertEqual(self.pat_saliente.servicio_asignado, self.guardia)

    def test_editar_intercambio(self):
        intercambio = Intercambio.objects.create(
            servicio_afectado=self.enfermeria, servicio_beneficiario=self.guardia,
            detalle_saliente="Notebook sin patrimonio", creado_por=self.user,
        )
        r = self.client.post(f"/intercambios/{intercambio.pk}/editar/", {
            "servicio_afectado": self.enfermeria.pk,
            "servicio_beneficiario": self.guardia.pk,
            "patrimonio_saliente": self.pat_saliente.pk,
            "motivo": "Corrección: sí tenía patrimonio",
            "fecha_intercambio": "2026-01-02T09:00",
        })
        self.assertEqual(r.status_code, 302)
        intercambio.refresh_from_db()
        self.assertEqual(intercambio.patrimonio_saliente, self.pat_saliente)
        self.assertEqual(intercambio.motivo, "Corrección: sí tenía patrimonio")
        self.pat_saliente.refresh_from_db()
        self.assertEqual(self.pat_saliente.servicio_asignado, self.guardia)

    def test_crear_intercambio_con_pedidos_vinculados(self):
        pedido_origen = Pedido.objects.create(numero="P-100")
        pedido_esperado = Pedido.objects.create(numero="P-200")

        r = self.client.post("/intercambios/nuevo/", {
            "servicio_afectado": self.enfermeria.pk,
            "servicio_beneficiario": self.guardia.pk,
            "patrimonio_saliente": self.pat_saliente.pk,
            "pedido_saliente": pedido_origen.pk,
            "fecha_intercambio": "2026-01-01T10:00",
        })
        self.assertEqual(r.status_code, 302)
        intercambio = Intercambio.objects.get()
        self.assertEqual(intercambio.pedido_saliente, pedido_origen)
        self.assertIsNone(intercambio.pedido_entrante)

        r = self.client.post(f"/intercambios/{intercambio.pk}/resolver/", {
            "patrimonio_entrante": self.pat_entrante.pk,
            "pedido_entrante": pedido_esperado.pk,
        })
        self.assertEqual(r.status_code, 302)
        intercambio.refresh_from_db()
        self.assertEqual(intercambio.pedido_entrante, pedido_esperado)

    def test_crear_intercambio_sin_patrimonio_ni_detalle_falla(self):
        r = self.client.post("/intercambios/nuevo/", {
            "servicio_afectado": self.enfermeria.pk,
            "servicio_beneficiario": self.guardia.pk,
            "fecha_intercambio": "2026-01-01T10:00",
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Intercambio.objects.exists())

    def test_resolver_intercambio_actualiza_servicio_entrante(self):
        intercambio = Intercambio.objects.create(
            servicio_afectado=self.enfermeria, servicio_beneficiario=self.guardia,
            patrimonio_saliente=self.pat_saliente, creado_por=self.user,
        )
        r = self.client.post(f"/intercambios/{intercambio.pk}/resolver/", {
            "patrimonio_entrante": self.pat_entrante.pk,
        })
        self.assertEqual(r.status_code, 302)
        intercambio.refresh_from_db()
        self.assertEqual(intercambio.estado, "RESUELTO")
        self.assertIsNotNone(intercambio.fecha_resolucion)
        self.pat_entrante.refresh_from_db()
        self.assertEqual(self.pat_entrante.servicio_asignado, self.enfermeria)

    def test_cancelar_intercambio_pendiente(self):
        intercambio = Intercambio.objects.create(
            servicio_afectado=self.enfermeria, servicio_beneficiario=self.guardia,
            detalle_saliente="Notebook sin patrimonio", creado_por=self.user,
        )
        r = self.client.post(f"/intercambios/{intercambio.pk}/cancelar/")
        self.assertEqual(r.status_code, 302)
        intercambio.refresh_from_db()
        self.assertEqual(intercambio.estado, "CANCELADO")


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


# ============================================================
# SERVICIO — vista de detalle (expediente completo)
# ============================================================

class ServicioDetailTest(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser("admin3", "admin3@test.com", "pw1234")
        self.client.force_login(self.user)
        self.servicio = Servicio.objects.create(nombre="Terapia Intensiva")

    def test_servicio_detail_vacio_ok(self):
        r = self.client.get(f"/servicios/{self.servicio.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Terapia Intensiva")

    def test_servicio_detail_404_si_no_existe(self):
        r = self.client.get("/servicios/99999/")
        self.assertEqual(r.status_code, 404)

    def test_servicio_detail_con_datos_relacionados(self):
        ActivoPC.objects.create(nombre_pc="PC-TI-01", servicio=self.servicio, activo=True)

        toner = Toner.objects.create(nombre="TK-1110", marca="Kyocera")
        item = item_de_toner(toner)
        mov = Movimiento.objects.create(tipo="EGRESO", servicio=self.servicio)
        MovimientoDetalle.objects.create(movimiento=mov, item=item, cantidad=2)

        impresora = Impresora.objects.create(marca="Brother", modelo="HL-1212", tipo="Laser", conexion="USB")
        AsignacionImpresora.objects.create(impresora=impresora, servicio=self.servicio)

        prestable_item = item_de_articulo(Articulo.objects.create(nombre="Proyector"))
        prestable_item.prestable = True
        prestable_item.save(update_fields=["prestable"])
        prestamo = Prestamo.objects.create(servicio=self.servicio)
        PrestamoDetalle.objects.create(prestamo=prestamo, item=prestable_item, cantidad=1)

        Reparacion.objects.create(item=item, servicio=self.servicio)

        pedido = Pedido.objects.create(numero="PED-001")
        pedido.servicios.add(self.servicio)

        Nota.objects.create(numero="N-001", servicio_solicitante=self.servicio)

        PatrimonioUnidad.objects.create(
            numero_patrimonio="PAT-001", servicio_asignado=self.servicio, asignado_por=self.user,
        )

        r = self.client.get(f"/servicios/{self.servicio.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "PC-TI-01")
        self.assertContains(r, "Brother")
        self.assertContains(r, "PED-001")
        self.assertContains(r, "PAT-001")

    def test_servicio_detail_muestra_pedidos_y_notas_en_el_resumen(self):
        # Pedidos y notas deben verse sin entrar a la solapa Documentación.
        pedido = Pedido.objects.create(numero="PED-777")
        pedido.servicios.add(self.servicio)
        Nota.objects.create(numero="N-777", servicio_solicitante=self.servicio)

        r = self.client.get(f"/servicios/{self.servicio.pk}/")
        content = r.content.decode()
        resumen_start = content.index('data-tab-panel="resumen"')
        documentacion_start = content.index('data-tab-panel="documentacion"')
        resumen_html = content[resumen_start:documentacion_start]
        self.assertIn("PED-777", resumen_html)
        self.assertIn("N-777", resumen_html)

    def test_servicio_detail_click_en_pc_va_al_detalle_no_a_editar(self):
        pc = ActivoPC.objects.create(nombre_pc="PC-TI-02", servicio=self.servicio, activo=True)
        r = self.client.get(f"/servicios/{self.servicio.pk}/")
        self.assertContains(r, f"/pcs/{pc.pk}/\"")

    def test_servicio_detail_tiene_boton_para_agregar_pc(self):
        r = self.client.get(f"/servicios/{self.servicio.pk}/")
        self.assertContains(r, f"/pcs/nuevo/?servicio={self.servicio.pk}")

    def test_servicio_detail_tiene_boton_para_agregar_articulo(self):
        r = self.client.get(f"/servicios/{self.servicio.pk}/")
        self.assertContains(r, f"/patrimonios/nuevo/?servicio={self.servicio.pk}")


class PcCreateConServicioPreseleccionadoTest(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser("admin5", "admin5@test.com", "pw1234")
        self.client.force_login(self.user)
        self.servicio = Servicio.objects.create(nombre="Guardia")

    def test_get_preselecciona_el_servicio(self):
        r = self.client.get(f"/pcs/nuevo/?servicio={self.servicio.pk}")
        self.assertContains(r, f'value="{self.servicio.pk}" selected')

    def test_post_con_next_redirige_ahi(self):
        r = self.client.post(
            f"/pcs/nuevo/?servicio={self.servicio.pk}",
            {"nombre_pc": "PC-GUARDIA-01", "servicio": self.servicio.pk, "next": f"/servicios/{self.servicio.pk}/#equipamiento"},
        )
        self.assertRedirects(r, f"/servicios/{self.servicio.pk}/#equipamiento", fetch_redirect_response=False)
        self.assertTrue(ActivoPC.objects.filter(nombre_pc="PC-GUARDIA-01", servicio=self.servicio).exists())


class PatrimonioStandaloneCreateConServicioPreseleccionadoTest(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser("admin6", "admin6@test.com", "pw1234")
        self.client.force_login(self.user)
        self.servicio = Servicio.objects.create(nombre="Guardia")
        self.articulo = Articulo.objects.create(nombre="Monitor Samsung", es_patrimonial=True)

    def test_get_preselecciona_el_servicio(self):
        r = self.client.get(f"/patrimonios/nuevo/?servicio={self.servicio.pk}")
        self.assertContains(r, f'value="{self.servicio.pk}" selected')

    def test_post_con_next_redirige_ahi(self):
        r = self.client.post(
            f"/patrimonios/nuevo/?servicio={self.servicio.pk}",
            {
                "articulo": self.articulo.pk, "numero_patrimonio": "PAT-GUARDIA-01",
                "servicio_asignado": self.servicio.pk, "next": f"/servicios/{self.servicio.pk}/#equipamiento",
            },
        )
        self.assertRedirects(r, f"/servicios/{self.servicio.pk}/#equipamiento", fetch_redirect_response=False)
        self.assertTrue(PatrimonioUnidad.objects.filter(numero_patrimonio="PAT-GUARDIA-01", servicio_asignado=self.servicio).exists())


class HistorialServicioTest(TestCase):
    def setUp(self):
        self.servicio = Servicio.objects.create(nombre="Guardia")
        self.toner = Toner.objects.create(nombre="CE285A", marca="HP")
        self.item = item_de_toner(self.toner)

    def test_historial_incluye_movimiento_con_color_correcto(self):
        mov = Movimiento.objects.create(tipo="INGRESO", servicio=self.servicio)
        MovimientoDetalle.objects.create(movimiento=mov, item=self.item, cantidad=5)

        eventos = historial_de_servicio(self.servicio)
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0]["tipo"], "movimiento_ingreso")
        self.assertEqual(eventos[0]["color"], "ok")

    def test_historial_ordenado_por_fecha_descendente(self):
        from django.utils import timezone
        mov1 = Movimiento.objects.create(
            tipo="INGRESO", servicio=self.servicio, fecha=timezone.now() - timezone.timedelta(days=5),
        )
        MovimientoDetalle.objects.create(movimiento=mov1, item=self.item, cantidad=5)
        mov2 = Movimiento.objects.create(tipo="EGRESO", servicio=self.servicio, fecha=timezone.now())
        MovimientoDetalle.objects.create(movimiento=mov2, item=self.item, cantidad=1)

        eventos = historial_de_servicio(self.servicio)
        self.assertEqual(eventos[0]["tipo"], "movimiento_egreso")
        self.assertEqual(eventos[1]["tipo"], "movimiento_ingreso")

    def test_historial_mezcla_fechas_date_y_datetime_sin_lanzar(self):
        # AsignacionImpresora.fecha_desde es date; Movimiento.fecha es datetime.
        # No debe lanzar TypeError al ordenar ambos tipos juntos.
        mov = Movimiento.objects.create(tipo="INGRESO", servicio=self.servicio)
        MovimientoDetalle.objects.create(movimiento=mov, item=self.item, cantidad=5)
        impresora = Impresora.objects.create(marca="HP", modelo="404", tipo="Laser", conexion="USB")
        AsignacionImpresora.objects.create(impresora=impresora, servicio=self.servicio)

        eventos = historial_de_servicio(self.servicio)
        self.assertEqual(len(eventos), 2)


# ============================================================
# VISTAS DE DETALLE POR ENTIDAD
# ============================================================

class EntidadDetailTest(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser("admin4", "admin4@test.com", "pw1234")
        self.client.force_login(self.user)
        self.servicio = Servicio.objects.create(nombre="Farmacia")

    def test_toner_detail_vacio_ok(self):
        toner = Toner.objects.create(nombre="CE285A", marca="HP")
        r = self.client.get(f"/toner/{toner.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "CE285A")

    def test_toner_detail_muestra_stock_y_movimientos(self):
        toner = Toner.objects.create(nombre="TK-1110", marca="Kyocera")
        item = item_de_toner(toner)
        mov = Movimiento.objects.create(tipo="INGRESO", servicio=self.servicio)
        MovimientoDetalle.objects.create(movimiento=mov, item=item, cantidad=7)

        r = self.client.get(f"/toner/{toner.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "TK-1110")
        # el stock (7) aparece en la página
        self.assertContains(r, ">7<")

    def test_toner_detail_muestra_impresoras_compatibles(self):
        toner = Toner.objects.create(nombre="CE285A", marca="HP")
        Impresora.objects.create(marca="HP", modelo="1102", tipo="Laser", conexion="USB", toner=toner)
        r = self.client.get(f"/toner/{toner.pk}/")
        self.assertContains(r, "1102")

    def test_toner_detail_marca_stock_negativo_como_inconsistente(self):
        # Stock negativo histórico (de antes de la validación) debe marcarse
        # visualmente, no ocultarse.
        toner = Toner.objects.create(nombre="TK-1110", marca="Kyocera")
        item = item_de_toner(toner)
        mov = Movimiento.objects.create(tipo="EGRESO", servicio=self.servicio, anulado=False)
        MovimientoDetalle.objects.create(movimiento=mov, item=item, cantidad=3)
        # fuerza el egreso directo en la DB para simular el estado histórico
        # (sin pasar por la validación, que ahora lo bloquearía)
        r = self.client.get(f"/toner/{toner.pk}/")
        self.assertContains(r, "Dato histórico inconsistente")

    def test_articulo_detail_vacio_ok(self):
        articulo = Articulo.objects.create(nombre="Mouse óptico")
        r = self.client.get(f"/articulos/{articulo.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Mouse óptico")

    def test_articulo_detail_patrimonial_muestra_unidades(self):
        articulo = Articulo.objects.create(nombre="Notebook", es_patrimonial=True)
        PatrimonioUnidad.objects.create(
            numero_patrimonio="PAT-777", articulo=articulo,
            servicio_asignado=self.servicio, asignado_por=self.user,
        )
        r = self.client.get(f"/articulos/{articulo.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "PAT-777")

    def test_pc_detail_vacio_ok(self):
        pc = ActivoPC.objects.create(nombre_pc="PC-FARM-01", servicio=self.servicio)
        r = self.client.get(f"/pcs/{pc.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "PC-FARM-01")

    def test_pc_detail_muestra_reparaciones(self):
        pc = ActivoPC.objects.create(nombre_pc="PC-FARM-02", servicio=self.servicio)
        item = item_de_pc(pc)
        Reparacion.objects.create(item=item, servicio=self.servicio, diagnostico="No enciende")
        r = self.client.get(f"/pcs/{pc.pk}/")
        self.assertContains(r, "No enciende")

    def test_impresora_detail_vacio_ok(self):
        impresora = Impresora.objects.create(marca="Brother", modelo="HL-1212", tipo="Laser", conexion="USB")
        r = self.client.get(f"/impresoras/{impresora.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "HL-1212")

    def test_impresora_detail_muestra_historial_de_asignaciones(self):
        impresora = Impresora.objects.create(marca="Brother", modelo="HL-1212", tipo="Laser", conexion="USB")
        AsignacionImpresora.objects.create(impresora=impresora, servicio=self.servicio, ubicacion="Mostrador")
        r = self.client.get(f"/impresoras/{impresora.pk}/")
        self.assertContains(r, "Farmacia")
        self.assertContains(r, "Mostrador")

    def test_impresora_detail_muestra_reparaciones(self):
        impresora = Impresora.objects.create(marca="Brother", modelo="HL-1212", tipo="Laser", conexion="USB")
        item = item_de_impresora(impresora)
        Reparacion.objects.create(item=item, diagnostico="Atasco de papel")
        r = self.client.get(f"/impresoras/{impresora.pk}/")
        self.assertContains(r, "Atasco de papel")

    def test_impresora_toggle_requiere_post(self):
        impresora = Impresora.objects.create(marca="HP", modelo="404", tipo="Laser", conexion="USB", estado="ACTIVA")
        r_get = self.client.get(f"/impresoras/{impresora.pk}/toggle/")
        self.assertEqual(r_get.status_code, 405)

        r_post = self.client.post(f"/impresoras/{impresora.pk}/toggle/")
        self.assertEqual(r_post.status_code, 302)
        impresora.refresh_from_db()
        self.assertEqual(impresora.estado, "INACTIVA")

    @patch("inventario.views.pcs.hacer_ping")
    def test_pc_ping_online(self, mock_ping):
        mock_ping.return_value = True
        pc = ActivoPC.objects.create(nombre_pc="PC-FARM-03", ip="10.0.0.5", servicio=self.servicio)
        r = self.client.get(f"/pcs/{pc.pk}/ping/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"online": True})
        mock_ping.assert_called_once_with("10.0.0.5")

    @patch("inventario.views.pcs.hacer_ping")
    def test_pc_ping_offline(self, mock_ping):
        mock_ping.return_value = False
        pc = ActivoPC.objects.create(nombre_pc="PC-FARM-04", ip="10.0.0.6", servicio=self.servicio)
        r = self.client.get(f"/pcs/{pc.pk}/ping/")
        self.assertEqual(r.json(), {"online": False})

    def test_pc_ping_sin_ip(self):
        pc = ActivoPC.objects.create(nombre_pc="PC-FARM-05", servicio=self.servicio)
        r = self.client.get(f"/pcs/{pc.pk}/ping/")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["online"])

    @patch("inventario.views.impresoras.hacer_ping")
    def test_impresora_ping_online(self, mock_ping):
        mock_ping.return_value = True
        impresora = Impresora.objects.create(
            marca="HP", modelo="M404", tipo="Laser", conexion="IP", ip="10.0.0.20",
        )
        r = self.client.get(f"/impresoras/{impresora.pk}/ping/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"online": True})
        mock_ping.assert_called_once_with("10.0.0.20")

    def test_impresora_ping_sin_ip(self):
        impresora = Impresora.objects.create(marca="HP", modelo="404", tipo="Laser", conexion="USB")
        r = self.client.get(f"/impresoras/{impresora.pk}/ping/")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["online"])

    def test_patrimonio_detail_independiente_ok(self):
        articulo = Articulo.objects.create(nombre="Notebook", es_patrimonial=True)
        pat = PatrimonioUnidad.objects.create(
            numero_patrimonio="PAT-900", articulo=articulo,
            servicio_asignado=self.servicio, asignado_por=self.user,
        )
        r = self.client.get(f"/patrimonios/{pat.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "PAT-900")
        self.assertContains(r, "independiente")

    def test_patrimonio_detail_muestra_datos_de_equipo(self):
        pat = PatrimonioUnidad.objects.create(
            numero_patrimonio="PAT-901", nombre_pc="PC-FARM-03", ip="10.0.0.5",
            usuario_asignado="jperez", asignado_por=self.user,
        )
        r = self.client.get(f"/patrimonios/{pat.pk}/")
        self.assertContains(r, "PC-FARM-03")
        self.assertContains(r, "10.0.0.5")
        self.assertContains(r, "jperez")

    def test_patrimonio_detail_muestra_donacion(self):
        pat = PatrimonioUnidad.objects.create(
            numero_patrimonio="PAT-902", es_donacion=True, donante="Fundación XYZ",
            asignado_por=self.user,
        )
        r = self.client.get(f"/patrimonios/{pat.pk}/")
        self.assertContains(r, "Donación")
        self.assertContains(r, "Fundación XYZ")

    def test_patrimonio_detail_muestra_link_al_pedido_de_origen(self):
        articulo = Articulo.objects.create(nombre="Monitor", es_patrimonial=True)
        item = item_de_articulo(articulo)
        pedido = Pedido.objects.create(numero="PED-500")
        detalle = PedidoDetalle.objects.create(pedido=pedido, item=item, cantidad=1)
        pat = PatrimonioUnidad.objects.create(
            numero_patrimonio="PAT-903", pedido_detalle=detalle, asignado_por=self.user,
        )
        r = self.client.get(f"/patrimonios/{pat.pk}/")
        self.assertContains(r, "PED-500")


# ============================================================
# LISTADOS — orden y filtros
# ============================================================

class ListadosOrdenServicioTest(TestCase):
    def test_ordenar_por_defecto_ascendente(self):
        Servicio.objects.create(nombre="Zeta")
        Toner.objects.create(nombre="Z", marca="Marca Z")
        Toner.objects.create(nombre="A", marca="Marca A")
        qs, clave, direccion = ordenar(
            self._request(), Toner.objects.all(),
            campos={"marca": "marca"}, default="marca",
        )
        self.assertEqual(clave, "marca")
        self.assertEqual(direccion, "asc")
        self.assertEqual(list(qs.values_list("marca", flat=True)), ["Marca A", "Marca Z"])

    def test_direccion_default_desc_cuando_se_pide(self):
        Toner.objects.create(nombre="Z", marca="Marca Z")
        Toner.objects.create(nombre="A", marca="Marca A")
        qs, clave, direccion = ordenar(
            self._request(), Toner.objects.all(),
            campos={"marca": "marca"}, default="marca", direccion_default="desc",
        )
        self.assertEqual(direccion, "desc")
        self.assertEqual(list(qs.values_list("marca", flat=True)), ["Marca Z", "Marca A"])

    def test_campo_no_permitido_cae_al_default(self):
        qs, clave, direccion = ordenar(
            self._request(sort="__raro__"), Toner.objects.all(),
            campos={"marca": "marca"}, default="marca",
        )
        self.assertEqual(clave, "marca")

    def _request(self, **params):
        from django.test import RequestFactory
        return RequestFactory().get("/", params)


class ListadosFiltrosVistaTest(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser("admin5", "admin5@test.com", "pw1234")
        self.client.force_login(self.user)

    def test_toner_filtro_estado_activo(self):
        Toner.objects.create(nombre="Activo1", activo=True)
        Toner.objects.create(nombre="Inactivo1", activo=False)
        r = self.client.get("/toner/?estado=inactivo")
        self.assertContains(r, "Inactivo1")
        self.assertNotContains(r, "Activo1")

    def test_impresoras_filtro_estado(self):
        Impresora.objects.create(marca="HP", modelo="ModeloUno", tipo="Laser", conexion="USB", estado="ACTIVA")
        Impresora.objects.create(marca="Brother", modelo="ModeloDos", tipo="Laser", conexion="USB", estado="INACTIVA")
        r = self.client.get("/impresoras/?estado=INACTIVA")
        self.assertContains(r, "ModeloDos")
        self.assertNotContains(r, "ModeloUno")

    def test_prestamos_filtro_por_servicio_y_estado(self):
        s1 = Servicio.objects.create(nombre="Quirófano")
        s2 = Servicio.objects.create(nombre="Rayos")
        Prestamo.objects.create(servicio=s1, entregado_a="Persona Q")
        Prestamo.objects.create(servicio=s2, entregado_a="Persona R")

        r = self.client.get(f"/prestamos/?servicio={s1.pk}")
        self.assertContains(r, "Persona Q")
        self.assertNotContains(r, "Persona R")

    def test_prestamos_orden_por_defecto_es_mas_reciente_primero(self):
        s = Servicio.objects.create(nombre="Quirófano")
        Prestamo.objects.create(servicio=s, entregado_a="Viejo", fecha_retiro=timezone.now() - timezone.timedelta(days=10))
        Prestamo.objects.create(servicio=s, entregado_a="Nuevo", fecha_retiro=timezone.now())
        r = self.client.get("/prestamos/")
        contenido = r.content.decode("utf-8")
        self.assertLess(contenido.index("Nuevo"), contenido.index("Viejo"))


# ============================================================
# BÚSQUEDA INSENSIBLE A ACENTOS (server-side)
# ============================================================

class BuscarTextoTest(TestCase):
    """buscar_texto() — usado por servicios_page y busqueda_global."""

    def test_encuentra_ignorando_acentos_y_mayusculas(self):
        from inventario.services.busqueda import buscar_texto
        Servicio.objects.create(nombre="Clínica Médica")
        r = buscar_texto(Servicio.objects.all(), "clinica medica", "nombre")
        self.assertEqual(list(r.values_list("nombre", flat=True)), ["Clínica Médica"])

    def test_termino_vacio_no_filtra(self):
        from inventario.services.busqueda import buscar_texto
        Servicio.objects.create(nombre="Guardia")
        r = buscar_texto(Servicio.objects.all(), "", "nombre")
        self.assertEqual(r.count(), 1)


class ServiciosPageBusquedaTest(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser("admin7", "admin7@test.com", "pw1234")
        self.client.force_login(self.user)

    def test_busqueda_de_servicios_ignora_acentos(self):
        Servicio.objects.create(nombre="Enfermería")
        r = self.client.get("/servicios/?q=enfermeria")
        self.assertContains(r, "Enfermería")


class BusquedaGlobalIgnoraAcentosTest(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser("admin8", "admin8@test.com", "pw1234")
        self.client.force_login(self.user)

    def test_encuentra_servicio_sin_tildes(self):
        Servicio.objects.create(nombre="Clínica")
        r = self.client.get("/buscar/?q=clinica")
        self.assertContains(r, "Clínica")


# ============================================================
# "VOLVER" DESDE UN PEDIDO/NOTA VUELVE AL SERVICIO (no siempre al listado)
# ============================================================

class PedidoDetailVolverTest(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser("admin9", "admin9@test.com", "pw1234")
        self.client.force_login(self.user)
        self.servicio = Servicio.objects.create(nombre="Guardia")
        self.pedido = Pedido.objects.create(numero="PED-TEST-01")
        self.pedido.servicios.add(self.servicio)

    def test_sin_next_vuelve_al_listado(self):
        r = self.client.get(f"/pedidos/{self.pedido.pk}/")
        self.assertContains(r, 'href="/pedidos/"')

    def test_con_next_vuelve_ahi(self):
        # el # va con %23 en la URL de la request (si no, el navegador/test
        # client lo toma como fragmento propio y nunca llega al server)
        next_url = f"/servicios/{self.servicio.pk}/#documentacion"
        r = self.client.get(f"/pedidos/{self.pedido.pk}/?next=/servicios/{self.servicio.pk}/%23documentacion")
        self.assertContains(r, f'href="{next_url}"')


class NotaDetailVolverTest(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser("admin10", "admin10@test.com", "pw1234")
        self.client.force_login(self.user)
        self.servicio = Servicio.objects.create(nombre="Guardia")
        self.nota = Nota.objects.create(servicio_solicitante=self.servicio)

    def test_sin_next_vuelve_al_listado(self):
        r = self.client.get(f"/notas/{self.nota.pk}/")
        self.assertContains(r, 'href="/notas/"')

    def test_con_next_vuelve_ahi(self):
        next_url = f"/servicios/{self.servicio.pk}/#documentacion"
        r = self.client.get(f"/notas/{self.nota.pk}/?next=/servicios/{self.servicio.pk}/%23documentacion")
        self.assertContains(r, f'href="{next_url}"')


# ============================================================
# buscar_texto() extendido al resto de los listados
# ============================================================

class BuscarTextoEnListadosTest(TestCase):
    """Spot-check de que buscar_texto() (accent-insensitive) quedó bien
    cableado en listados que antes usaban Q(...)__icontains directo,
    incluyendo los que necesitan .distinct() por relaciones a-muchos."""

    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser("admin11", "admin11@test.com", "pw1234")
        self.client.force_login(self.user)
        self.servicio = Servicio.objects.create(nombre="Quirófano")

    def test_toner_page_ignora_acentos(self):
        Toner.objects.create(nombre="Tóner genérico", marca="HP")
        r = self.client.get("/toner/?q=toner generico")
        self.assertContains(r, "Tóner genérico")

    def test_pcs_page_ignora_acentos_via_servicio(self):
        ActivoPC.objects.create(nombre_pc="PC-1", servicio=self.servicio)
        r = self.client.get("/pcs/?q=quirofano")
        self.assertContains(r, "PC-1")

    def test_movimientos_list_ignora_acentos(self):
        Movimiento.objects.create(tipo="EGRESO", servicio=self.servicio)
        r = self.client.get("/movimientos/?q=quirofano")
        self.assertContains(r, "Quirófano")

    def test_movimientos_list_no_duplica_filas_por_relacion_a_muchos(self):
        from inventario.services.busqueda import buscar_texto
        toner = Toner.objects.create(nombre="Genérico", marca="HP")
        item = item_de_toner(toner)
        mov = Movimiento.objects.create(tipo="EGRESO", servicio=self.servicio)
        MovimientoDetalle.objects.create(movimiento=mov, item=item, cantidad=1)
        qs = buscar_texto(
            Movimiento.objects.all(), "quirofano",
            "observaciones", "servicio__nombre",
            "detalles__item__toner__nombre", "detalles__item__articulo__nombre",
        ).distinct()
        self.assertEqual(qs.count(), 1)

    def test_prestamos_list_ignora_acentos(self):
        Prestamo.objects.create(servicio=self.servicio, entregado_a="Alguien")
        r = self.client.get("/prestamos/?q=quirofano")
        self.assertContains(r, "Alguien")

    def test_prestamos_list_no_duplica_filas_por_relacion_a_muchos(self):
        from inventario.services.busqueda import buscar_texto
        articulo = Articulo.objects.create(nombre="Proyector")
        item = item_de_articulo(articulo)
        item.prestable = True
        item.save(update_fields=["prestable"])
        prestamo = Prestamo.objects.create(servicio=self.servicio, entregado_a="Alguien")
        PrestamoDetalle.objects.create(prestamo=prestamo, item=item, cantidad=1)
        qs = buscar_texto(
            Prestamo.objects.all(), "quirofano",
            "servicio__nombre", "entregado_a", "observaciones",
            "detalles__detalle", "detalles__item__tipo",
        ).distinct()
        self.assertEqual(qs.count(), 1)

    def test_reparaciones_list_ignora_acentos_via_servicio(self):
        from inventario.models import Proveedor
        toner = Toner.objects.create(nombre="X", marca="HP")
        item = item_de_toner(toner)
        proveedor = Proveedor.objects.create(nombre="Técnica SRL")
        Reparacion.objects.create(item=item, proveedor=proveedor, servicio=self.servicio)
        r = self.client.get("/reparaciones/?q=quirofano")
        self.assertContains(r, "Técnica SRL")

    def test_intercambios_list_ignora_acentos_via_servicio(self):
        otro = Servicio.objects.create(nombre="Guardia")
        Intercambio.objects.create(
            servicio_afectado=self.servicio, servicio_beneficiario=otro,
            creado_por=self.user, motivo="Compensación urgente",
        )
        r = self.client.get("/intercambios/?q=quirofano")
        self.assertContains(r, '<span class="chip">1</span>')

    def test_patrimonios_list_ignora_acentos_via_servicio(self):
        PatrimonioUnidad.objects.create(
            numero_patrimonio="PAT-QUIROFANO-01",
            servicio_asignado=self.servicio,
            asignado_por=self.user,
        )
        r = self.client.get("/patrimonios/?q=quirofano")
        self.assertContains(r, "PAT-QUIROFANO-01")


# ============================================================
# N+1: la cantidad de queries no debe escalar con la cantidad de filas
# ============================================================

class SinNMasUnoTest(TestCase):
    """Regresión para dos N+1 reales encontrados con CaptureQueriesContext:
    Impresora.asignacion_activa (bypaseaba el prefetch) y el combo de
    Nota en PendienteForm (Nota.__str__ toca servicio_solicitante sin
    select_related). En ambos, la cantidad de queries para la página no
    tiene que crecer según cuántas filas haya."""

    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.user = User.objects.create_superuser("admin12", "admin12@test.com", "pw1234")
        self.client.force_login(self.user)

    def _queries_para(self, url):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(url)
        return len(ctx.captured_queries)

    def test_impresoras_page_no_escala_con_la_cantidad_de_impresoras(self):
        servicio = Servicio.objects.create(nombre="Guardia")
        for i in range(2):
            imp = Impresora.objects.create(marca="HP", modelo=f"M{i}")
            AsignacionImpresora.objects.create(impresora=imp, servicio=servicio)
        pocas = self._queries_para("/impresoras/")

        for i in range(2, 8):
            imp = Impresora.objects.create(marca="HP", modelo=f"M{i}")
            AsignacionImpresora.objects.create(impresora=imp, servicio=servicio)
        muchas = self._queries_para("/impresoras/")

        self.assertEqual(pocas, muchas)

    def test_pendientes_page_no_escala_con_la_cantidad_de_notas(self):
        servicio = Servicio.objects.create(nombre="Guardia")
        for i in range(2):
            Nota.objects.create(servicio_solicitante=servicio, numero=f"N-{i}")
        pocas = self._queries_para("/pendientes/")

        for i in range(2, 8):
            Nota.objects.create(servicio_solicitante=servicio, numero=f"N-{i}")
        muchas = self._queries_para("/pendientes/")

        self.assertEqual(pocas, muchas)


# ============================================================
# generar_ficha_desde_articulo() — sin ningún test hasta ahora
# ============================================================

class GenerarFichaDesdeArticuloTest(TestCase):
    """Auto-genera la ficha completa (Impresora/ActivoPC) de una unidad
    patrimonial cuando el artículo de catálogo lo tiene configurado.
    Cero cobertura antes de este test a pesar de tener idempotencia
    documentada en el docstring y nunca verificada."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser("admin13", "admin13@test.com", "pw1234")
        self.servicio = Servicio.objects.create(nombre="Guardia")

    def _unidad(self, **extra):
        defaults = dict(numero_patrimonio="PAT-100", asignado_por=self.user)
        defaults.update(extra)
        return PatrimonioUnidad(**defaults)

    def test_no_hace_nada_si_el_articulo_no_genera_ficha(self):
        from inventario.services.patrimonios import generar_ficha_desde_articulo
        articulo = Articulo.objects.create(nombre="Mouse", genera_ficha="")
        unidad = self._unidad()
        generar_ficha_desde_articulo(unidad, articulo)
        self.assertFalse(Impresora.objects.exists())
        self.assertFalse(ActivoPC.objects.exists())

    def test_genera_impresora_con_servicio_asignado(self):
        from inventario.services.patrimonios import generar_ficha_desde_articulo
        articulo = Articulo.objects.create(nombre="Impresora HP", marca="HP", genera_ficha="IMPRESORA")
        unidad = self._unidad(
            numero_patrimonio="PAT-200", ip="192.168.1.50",
            servicio_asignado=self.servicio, usuario_asignado="Juan",
        )
        generar_ficha_desde_articulo(unidad, articulo)

        impresora = Impresora.objects.get(patrimonio="PAT-200")
        self.assertEqual(impresora.marca, "HP")
        self.assertEqual(impresora.conexion, "IP")
        self.assertEqual(impresora.ip, "192.168.1.50")
        self.assertEqual(impresora.servicio_actual, self.servicio)
        self.assertEqual(impresora.responsable_actual, "Juan")

    def test_genera_impresora_es_idempotente(self):
        from inventario.services.patrimonios import generar_ficha_desde_articulo
        articulo = Articulo.objects.create(nombre="Impresora HP", marca="HP", genera_ficha="IMPRESORA")
        unidad = self._unidad(numero_patrimonio="PAT-300")
        generar_ficha_desde_articulo(unidad, articulo)
        generar_ficha_desde_articulo(unidad, articulo)
        self.assertEqual(Impresora.objects.filter(patrimonio="PAT-300").count(), 1)

    def test_ip_invalida_no_rompe_y_usa_usb(self):
        from inventario.services.patrimonios import generar_ficha_desde_articulo
        articulo = Articulo.objects.create(nombre="Impresora HP", marca="HP", genera_ficha="IMPRESORA")
        unidad = self._unidad(numero_patrimonio="PAT-400", ip="no-es-una-ip")
        generar_ficha_desde_articulo(unidad, articulo)

        impresora = Impresora.objects.get(patrimonio="PAT-400")
        self.assertEqual(impresora.conexion, "USB")
        self.assertIsNone(impresora.ip)

    def test_genera_activo_pc(self):
        from inventario.services.patrimonios import generar_ficha_desde_articulo
        articulo = Articulo.objects.create(nombre="PC de escritorio", genera_ficha="ACTIVO_PC")
        unidad = self._unidad(
            numero_patrimonio="PAT-500", nombre_pc="PC-GUARDIA-01",
            serial="SN123", servicio_asignado=self.servicio,
        )
        generar_ficha_desde_articulo(unidad, articulo)

        pc = ActivoPC.objects.get(patrimonio="PAT-500")
        self.assertEqual(pc.nombre_pc, "PC-GUARDIA-01")
        self.assertEqual(pc.serie, "SN123")
        self.assertEqual(pc.servicio, self.servicio)


# ============================================================
# asignar_impresora_a_servicio() — "única fuente de verdad" sin tests directos
# ============================================================

class AsignarImpresoraAServicioTest(TestCase):
    def setUp(self):
        self.a = Servicio.objects.create(nombre="Guardia")
        self.b = Servicio.objects.create(nombre="Farmacia")
        self.impresora = Impresora.objects.create(marca="HP", modelo="X")

    def test_primera_asignacion(self):
        from inventario.services.impresoras import asignar_impresora_a_servicio
        asignar_impresora_a_servicio(self.impresora, self.a, responsable="Ana")
        self.assertEqual(self.impresora.servicio_actual, self.a)
        self.assertEqual(AsignacionImpresora.objects.count(), 1)

    def test_reasignar_a_otro_servicio_cierra_la_anterior(self):
        from inventario.services.impresoras import asignar_impresora_a_servicio
        asignar_impresora_a_servicio(self.impresora, self.a)
        primera = AsignacionImpresora.objects.get(servicio=self.a)

        # misma instancia para las dos llamadas: asignacion_activa es
        # @cached_property, así que esto también prueba que la función
        # invalida su propio cache tras el UPDATE por queryset (si no,
        # el segundo self.impresora.servicio_actual de abajo devolvería
        # el valor viejo cacheado por la primera llamada).
        asignar_impresora_a_servicio(self.impresora, self.b)

        primera.refresh_from_db()
        self.assertIsNotNone(primera.fecha_hasta)
        self.assertEqual(self.impresora.servicio_actual, self.b)
        self.assertEqual(AsignacionImpresora.objects.count(), 2)

    def test_asignar_al_mismo_servicio_no_hace_nada(self):
        from inventario.services.impresoras import asignar_impresora_a_servicio
        asignar_impresora_a_servicio(self.impresora, self.a)
        resultado = asignar_impresora_a_servicio(self.impresora, self.a)
        self.assertIsNone(resultado)
        self.assertEqual(AsignacionImpresora.objects.count(), 1)

    def test_desasignar_cierra_sin_abrir_una_nueva(self):
        from inventario.services.impresoras import asignar_impresora_a_servicio
        asignar_impresora_a_servicio(self.impresora, self.a)
        asignar_impresora_a_servicio(self.impresora, None)

        self.assertIsNone(self.impresora.servicio_actual)
        self.assertEqual(AsignacionImpresora.objects.filter(fecha_hasta__isnull=True).count(), 0)


# ============================================================
# PEDIDO: FECHAS DE AUDITORÍA CONSISTENTES SIN IMPORTAR EL CAMINO
# ============================================================

class PedidoEstadoFechaTest(TestCase):
    """
    Antes, las fechas (fecha_aprobado/recibido/entregado) solo se
    completaban en la vista "Avanzar". Editar el estado desde el
    formulario normal dejaba el pedido en ese estado sin su fecha. Ahora
    la lógica vive en Pedido.save(), así que aplica sin importar el
    camino de entrada.
    """

    def setUp(self):
        self.pedido = Pedido.objects.create(numero="PED-2026-0001", estado="HECHO")

    def test_pasar_a_aprobado_completa_fecha_aprobado(self):
        self.pedido.estado = "APROBADO"
        self.pedido.save()
        self.pedido.refresh_from_db()
        self.assertIsNotNone(self.pedido.fecha_aprobado)

    def test_pasar_a_recibido_completa_fecha_recibido(self):
        self.pedido.estado = "RECIBIDO"
        self.pedido.save()
        self.pedido.refresh_from_db()
        self.assertIsNotNone(self.pedido.fecha_recibido)

    def test_pasar_a_entregado_completa_fecha_entregado(self):
        self.pedido.estado = "ENTREGADO"
        self.pedido.save()
        self.pedido.refresh_from_db()
        self.assertIsNotNone(self.pedido.fecha_entregado)

    def test_no_pisa_una_fecha_ya_cargada(self):
        from datetime import date
        vieja = date(2020, 1, 1)
        self.pedido.fecha_aprobado = vieja
        self.pedido.estado = "APROBADO"
        self.pedido.save()
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.fecha_aprobado, vieja)

    def test_avanzar_via_la_vista_sigue_completando_la_fecha(self):
        User = get_user_model()
        user = User.objects.create_superuser("pedadmin", "ped@test.com", "pw1234")
        self.client.force_login(user)

        r = self.client.post(f"/pedidos/{self.pedido.pk}/avanzar/")
        self.assertEqual(r.status_code, 302)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estado, "APROBADO")
        self.assertIsNotNone(self.pedido.fecha_aprobado)

    def test_editar_estado_desde_el_form_normal_tambien_completa_la_fecha(self):
        """
        Caso que antes fallaba (API-01): cambiar el estado desde el
        formulario de edición común, no desde "Avanzar".
        """
        User = get_user_model()
        user = User.objects.create_superuser("pedadmin2", "ped2@test.com", "pw1234")
        self.client.force_login(user)
        servicio = Servicio.objects.create(nombre="Quirófano")

        self.assertIsNone(self.pedido.fecha_entregado)
        r = self.client.post(f"/pedidos/{self.pedido.pk}/editar/", {
            "numero": self.pedido.numero,
            "servicios": [servicio.pk],
            "proveedor": "",
            "nota": "",
            "para_que": "",
            "observaciones": "",
            "estado": "ENTREGADO",
            "fecha_aprobado": "",
            "fecha_recibido": "",
            "fecha_entregado": "",
            "pedidos_relacionados": [],
            "detalles-TOTAL_FORMS": "0",
            "detalles-INITIAL_FORMS": "0",
            "detalles-MIN_NUM_FORMS": "0",
            "detalles-MAX_NUM_FORMS": "1000",
        })
        self.assertEqual(r.status_code, 302)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estado, "ENTREGADO")
        self.assertIsNotNone(self.pedido.fecha_entregado)


# ============================================================
# MOVIMIENTODETALLE: CANTIDAD SIEMPRE POSITIVA (constraint de DB)
# ============================================================

class MovimientoDetalleConstraintTest(TestCase):
    """
    cantidad=0 nunca tiene sentido en ningún tipo de movimiento (no hace
    nada), así que eso sí está bloqueado a nivel de base. cantidad
    negativa SIGUE permitida: en un AJUSTE es un delta con signo (ver
    StockServiceTest.test_ajuste_resta) — no se puede garantizar "siempre
    positiva" sin romper esa funcionalidad real y ya probada.
    """

    def setUp(self):
        self.servicio = Servicio.objects.create(nombre="Pediatría")
        self.toner = Toner.objects.create(nombre="TK-1110", marca="Kyocera")
        self.item = item_de_toner(self.toner)
        self.movimiento = Movimiento.objects.create(tipo="INGRESO", servicio=self.servicio)

    def test_cantidad_cero_directo_por_orm_falla(self):
        with self.assertRaises(IntegrityError):
            MovimientoDetalle.objects.create(movimiento=self.movimiento, item=self.item, cantidad=0)

    def test_cantidad_positiva_sigue_funcionando(self):
        detalle = MovimientoDetalle.objects.create(movimiento=self.movimiento, item=self.item, cantidad=3)
        self.assertEqual(detalle.cantidad, 3)

    def test_cantidad_negativa_sigue_permitida_para_ajuste(self):
        ajuste = Movimiento.objects.create(tipo="AJUSTE", servicio=self.servicio)
        detalle = MovimientoDetalle.objects.create(movimiento=ajuste, item=self.item, cantidad=-3)
        self.assertEqual(detalle.cantidad, -3)


# ============================================================
# MOVIMIENTO: TRAZABILIDAD DE USUARIO
# ============================================================

class MovimientoTrazabilidadTest(TestCase):
    """
    Todo movimiento de stock (y su anulación) debe quedar asociado a quién
    lo hizo — antes no había ningún campo de usuario en Movimiento.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser("trazaadmin", "traza@test.com", "pw1234")
        self.client.force_login(self.user)
        self.servicio = Servicio.objects.create(nombre="Pediatría")

    def test_movimiento_create_registra_quien_lo_creo(self):
        toner = Toner.objects.create(nombre="TK-1110", marca="Kyocera")
        mov = Movimiento.objects.create(tipo="INGRESO", servicio=self.servicio)
        MovimientoDetalle.objects.create(movimiento=mov, item=item_de_toner(toner), cantidad=5)

        r = self.client.post("/movimientos/nuevo/", {
            "tipo": "EGRESO",
            "servicio": self.servicio.pk,
            "fecha": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "toner-TOTAL_FORMS": "1",
            "toner-INITIAL_FORMS": "0",
            "toner-MIN_NUM_FORMS": "0",
            "toner-MAX_NUM_FORMS": "1000",
            "toner-0-toner": str(toner.pk),
            "toner-0-cantidad": "2",
            "art-TOTAL_FORMS": "0",
            "art-INITIAL_FORMS": "0",
            "art-MIN_NUM_FORMS": "0",
            "art-MAX_NUM_FORMS": "1000",
        })
        self.assertEqual(r.status_code, 302)
        egreso = Movimiento.objects.get(tipo="EGRESO")
        self.assertEqual(egreso.creado_por, self.user)

    def test_entrega_rapida_toner_registra_quien_la_hizo(self):
        toner = Toner.objects.create(nombre="TK-1110", marca="Kyocera")
        item = item_de_toner(toner)
        mov = Movimiento.objects.create(tipo="INGRESO", servicio=self.servicio)
        MovimientoDetalle.objects.create(movimiento=mov, item=item, cantidad=5)

        r = self.client.post("/toner/entrega/", {
            "servicio": self.servicio.pk,
            "toner": toner.pk,
            "cantidad": 2,
            "fecha": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        })
        self.assertEqual(r.status_code, 302)
        egreso = Movimiento.objects.get(tipo="EGRESO")
        self.assertEqual(egreso.creado_por, self.user)

    def test_entrega_rapida_articulo_registra_quien_la_hizo(self):
        articulo = Articulo.objects.create(nombre="Mouse óptico")
        item = item_de_articulo(articulo)
        mov = Movimiento.objects.create(tipo="INGRESO", servicio=self.servicio)
        MovimientoDetalle.objects.create(movimiento=mov, item=item, cantidad=5)

        r = self.client.post("/articulos/entrega/", {
            "servicio": self.servicio.pk,
            "articulo": articulo.pk,
            "cantidad": 1,
            "fecha": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        })
        self.assertEqual(r.status_code, 302)
        egreso = Movimiento.objects.get(tipo="EGRESO")
        self.assertEqual(egreso.creado_por, self.user)

    def test_anular_movimiento_registra_quien_y_cuando(self):
        mov = Movimiento.objects.create(tipo="INGRESO", servicio=self.servicio)
        self.assertIsNone(mov.anulado_por)
        self.assertIsNone(mov.fecha_anulado)

        r = self.client.post(f"/movimientos/{mov.pk}/anular/")
        self.assertEqual(r.status_code, 302)

        mov.refresh_from_db()
        self.assertTrue(mov.anulado)
        self.assertEqual(mov.anulado_por, self.user)
        self.assertIsNotNone(mov.fecha_anulado)

    def test_anular_movimiento_ya_anulado_no_pisa_quien_lo_anulo(self):
        User = get_user_model()
        otro = User.objects.create_superuser("otroadmin", "otro@test.com", "pw1234")
        mov = Movimiento.objects.create(tipo="INGRESO", servicio=self.servicio)

        self.client.post(f"/movimientos/{mov.pk}/anular/")
        mov.refresh_from_db()
        primer_anulador = mov.anulado_por

        self.client.force_login(otro)
        self.client.post(f"/movimientos/{mov.pk}/anular/")
        mov.refresh_from_db()
        self.assertEqual(mov.anulado_por, primer_anulador)


# ============================================================
# ADMIN: PERMISOS (gestión de usuarios y roles)
# ============================================================

class AdminPermisosTest(TestCase):
    """
    Cubre el único punto de escalamiento de privilegios del sistema: las
    vistas de inventario/views/admin.py, protegidas con @login_required +
    @solo_superadmin (is_superuser). No prueba el caso "anónimo" porque,
    con AutoLoginMiddleware activo, no existe un request realmente anónimo
    en esta app — eso ya está documentado como hallazgo de seguridad
    aparte (ver docs/auditoria).
    """

    def setUp(self):
        User = get_user_model()
        self.superadmin = User.objects.create_superuser("super1", "super1@test.com", "pw1234")
        self.comun = User.objects.create_user("comun1", "comun1@test.com", "pw1234")
        self.otro = User.objects.create_user("otro1", "otro1@test.com", "pw1234")

    def _rutas_protegidas(self):
        return [
            ("get", "/gestion/"),
            ("get", "/gestion/usuarios/"),
            ("get", "/gestion/usuarios/nuevo/"),
            ("get", f"/gestion/usuarios/{self.otro.pk}/editar/"),
            ("post", f"/gestion/usuarios/{self.otro.pk}/toggle/"),
            ("post", f"/gestion/usuarios/{self.otro.pk}/eliminar/"),
            ("get", "/gestion/roles/"),
            ("get", "/gestion/roles/nuevo/"),
        ]

    def test_usuario_no_superadmin_es_rechazado_en_todas_las_rutas(self):
        self.client.force_login(self.comun)
        for metodo, url in self._rutas_protegidas():
            with self.subTest(url=url):
                resp = self.client.get(url) if metodo == "get" else self.client.post(url)
                self.assertEqual(resp.status_code, 302)
                self.assertIn("/accounts/login/", resp.url)

        # Confirma que el rechazo es real: nada de lo que debería bloquearse pasó.
        self.otro.refresh_from_db()
        self.assertTrue(self.otro.is_active)
        User = get_user_model()
        self.assertTrue(User.objects.filter(pk=self.otro.pk).exists())

    def test_superadmin_puede_listar_usuarios_y_roles(self):
        self.client.force_login(self.superadmin)
        self.assertEqual(self.client.get("/gestion/usuarios/").status_code, 200)
        self.assertEqual(self.client.get("/gestion/roles/").status_code, 200)

    def test_superadmin_puede_crear_usuario(self):
        self.client.force_login(self.superadmin)
        User = get_user_model()
        resp = self.client.post("/gestion/usuarios/nuevo/", {
            "username": "nuevo1",
            "first_name": "", "last_name": "", "email": "",
            "is_active": "on",
            "groups": [],
            "password1": "contrasenia123",
            "password2": "contrasenia123",
        })
        self.assertRedirects(resp, "/gestion/usuarios/")
        self.assertTrue(User.objects.filter(username="nuevo1").exists())

    def test_superadmin_puede_activar_y_desactivar_usuario(self):
        self.client.force_login(self.superadmin)
        self.assertTrue(self.otro.is_active)
        self.client.post(f"/gestion/usuarios/{self.otro.pk}/toggle/")
        self.otro.refresh_from_db()
        self.assertFalse(self.otro.is_active)

    def test_superadmin_no_puede_desactivarse_a_si_mismo(self):
        self.client.force_login(self.superadmin)
        self.client.post(f"/gestion/usuarios/{self.superadmin.pk}/toggle/")
        self.superadmin.refresh_from_db()
        self.assertTrue(self.superadmin.is_active)

    def test_superadmin_puede_eliminar_usuario(self):
        self.client.force_login(self.superadmin)
        User = get_user_model()
        self.client.post(f"/gestion/usuarios/{self.otro.pk}/eliminar/")
        self.assertFalse(User.objects.filter(pk=self.otro.pk).exists())

    def test_superadmin_no_puede_eliminarse_a_si_mismo(self):
        self.client.force_login(self.superadmin)
        User = get_user_model()
        self.client.post(f"/gestion/usuarios/{self.superadmin.pk}/eliminar/")
        self.assertTrue(User.objects.filter(pk=self.superadmin.pk).exists())

    def test_superadmin_puede_crear_y_editar_rol(self):
        from django.contrib.auth.models import Group

        self.client.force_login(self.superadmin)
        resp = self.client.post("/gestion/roles/nuevo/", {"name": "Operador"})
        self.assertRedirects(resp, "/gestion/roles/")
        rol = Group.objects.get(name="Operador")

        resp = self.client.post(f"/gestion/roles/{rol.pk}/editar/", {"name": "Supervisor"})
        self.assertRedirects(resp, "/gestion/roles/")
        rol.refresh_from_db()
        self.assertEqual(rol.name, "Supervisor")

    def test_superadmin_puede_eliminar_rol(self):
        from django.contrib.auth.models import Group
        rol = Group.objects.create(name="Temporal")
        self.client.force_login(self.superadmin)
        self.client.post(f"/gestion/roles/{rol.pk}/eliminar/")
        self.assertFalse(Group.objects.filter(pk=rol.pk).exists())


# ============================================================
# BACKUP DE LA BASE (lo usa desktop_app.py antes de migrar)
# ============================================================

class RespaldarSqliteTest(TestCase):
    """
    Corre contra bases SQLite de prueba en un directorio temporal, nunca
    contra la base real de la app.
    """

    def _crear_db_sqlite(self, path):
        import sqlite3
        conn = sqlite3.connect(str(path))
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        conn.execute("INSERT INTO t (v) VALUES ('hola')")
        conn.commit()
        conn.close()

    def test_sin_base_no_hace_nada(self):
        import tempfile
        from pathlib import Path
        from inventario.services.backups import respaldar_sqlite

        with tempfile.TemporaryDirectory() as tmp:
            resultado = respaldar_sqlite(Path(tmp) / "no_existe.sqlite3", Path(tmp) / "backups")
            self.assertIsNone(resultado)

    def test_crea_un_backup_con_los_datos_de_la_base(self):
        import sqlite3
        import tempfile
        from pathlib import Path
        from inventario.services.backups import respaldar_sqlite

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "db.sqlite3"
            self._crear_db_sqlite(db_path)
            backups_dir = Path(tmp) / "backups"

            destino = respaldar_sqlite(db_path, backups_dir)

            self.assertIsNotNone(destino)
            self.assertTrue(destino.exists())
            conn = sqlite3.connect(str(destino))
            fila = conn.execute("SELECT v FROM t").fetchone()
            conn.close()
            self.assertEqual(fila[0], "hola")

    def test_rota_y_deja_solo_los_ultimos_N(self):
        import os
        import tempfile
        from pathlib import Path
        from inventario.services.backups import _rotar_backups

        with tempfile.TemporaryDirectory() as tmp:
            backups_dir = Path(tmp)
            archivos = []
            for i in range(5):
                archivo = backups_dir / f"db_000{i}.sqlite3"
                archivo.write_text("x")
                os.utime(archivo, (1000 + i, 1000 + i))  # mtime creciente controlado
                archivos.append(archivo)

            _rotar_backups(backups_dir, mantener=3)

            restantes = sorted(backups_dir.glob("db_*.sqlite3"))
            self.assertEqual(len(restantes), 3)
            # deben quedar los 3 más nuevos
            self.assertEqual(set(restantes), set(archivos[-3:]))
