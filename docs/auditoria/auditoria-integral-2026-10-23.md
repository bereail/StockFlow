# Auditoría integral de StockFlow — 2026-10-23

Auditoría de solo lectura. No se modificó código de la aplicación, no se ejecutaron migraciones contra la base real, no se tocaron datos de producción, no se instalaron ni actualizaron dependencias, no se inició ningún build ni despliegue.

> **Actualización 2026-10-23 (post-auditoría):** se implementó el P0 y el P1 completos.
>
> **P0:**
> - **OPS-004 + OPS-002** (sin backup / migración automática sin backup previo): resuelto. Nuevo módulo `inventario/services/backups.py` (`respaldar_sqlite`, con rotación) invocado desde `desktop_app.py` antes de `migrate --run-syncdb`, con 3 tests nuevos (`RespaldarSqliteTest`) que corren contra SQLite de prueba en un directorio temporal, nunca contra la base real.
> - **SEC-01** (`AutoLoginMiddleware`): decisión confirmada explícitamente con Berenice — se mantiene activo tal como está. No es un hallazgo "corregido", es una decisión de producto reconfirmada.
>
> **P1:**
> - **TEST-01** (admin sin tests): resuelto. Nueva clase `AdminPermisosTest` (9 tests) cubre las 9 rutas de `admin.py` — rechazo a usuario no-superadmin y CRUD completo de usuarios/roles con superadmin.
> - **STK-03** (Movimiento sin trazabilidad de usuario): resuelto. Campos `creado_por`, `anulado_por`, `fecha_anulado` agregados a `Movimiento`, completados en los 4 puntos de creación (`movimientos.py`, `toner.py`, `articulos.py`, `impresoras.py`) y en `movimiento_anular`. 5 tests nuevos (`MovimientoTrazabilidadTest`).
> - **API-01** (estado de Pedido editable sin completar fechas de auditoría): resuelto. Berenice confirmó que necesita poder corregir el estado a mano a veces, así que se mantuvo el campo editable y se movió la lógica de fechas a `Pedido.save()` (mismo patrón que ya usaba `Nota.save()`), para que aplique sin importar el camino de entrada. 6 tests nuevos (`PedidoEstadoFechaTest`), incluyendo el caso exacto que antes fallaba.
> - **DB-01** (sin constraint de DB para cantidad positiva en `MovimientoDetalle`): resuelto, **con una corrección sobre el hallazgo original**. Antes de aplicar, se verificó con una consulta de solo lectura contra la base real (autorizada explícitamente) que no había filas con `cantidad <= 0` (0 de 35) — la migración era segura de aplicar. Pero al implementar la constraint tal como la planteaba el hallazgo (`cantidad > 0`), **un test ya existente falló** (`test_ajuste_resta`): reveló que `cantidad` es un delta con signo para movimientos tipo `AJUSTE` (un ajuste a la baja es legítimamente negativo — ver `services/stock.py`), no "siempre positiva" como asumía el hallazgo original. Se corrigió la constraint a `cantidad != 0` (bloquea solo el caso sin sentido en cualquier tipo de movimiento: cantidad cero), que no rompe esa funcionalidad real. 3 tests nuevos (`MovimientoDetalleConstraintTest`), incluyendo uno que confirma que el ajuste negativo sigue permitido.
>
> Migraciones `0056` y `0057` generadas y aplicadas a la base real. Suite completa final: **195 tests, OK**.

---

## 1. Resumen ejecutivo

**Estado general del sistema:** sólido para su escala. Es un monolito Django de una sola app, bien organizado (separación clara de `views/`, `forms/`, `services/`, `templates/`), con una suite de 169 tests que pasa en verde, disciplina real de código (N+1 ya cazados y corregidos en el pasado, backfills correctos en la gran mayoría de migraciones, sin SQL crudo, sin `csrf_exempt`, secretos nunca commiteados). El riesgo más serio no es de código sino de **operación**: la base de datos real no tiene ningún backup automático y se migra sola en cada arranque de la app de escritorio.

**Fortalezas reales (confirmadas con evidencia):**
- El stock nunca se persiste como contador: siempre se recalcula desde el historial de movimientos (`services/stock.py`), lo que elimina por diseño la clase de bug "stock desincronizado del historial".
- Cobertura de `@login_required` y `@require_POST` consistente en los 16 módulos de vistas, sin excepciones encontradas.
- Sin SQL crudo, sin `csrf_exempt`, sin secretos en el repo (`SECRET_KEY` se genera una vez y se persiste fuera del código).
- N+1 ya resueltos en los listados principales (confirmado por trazado manual + un patrón de test de regresión ya existente, `SinNMasUnoTest`).
- `.gitignore` correcto: ningún archivo de base de datos ni backup quedó trackeado en git.
- Manejo de instancia única y puerto dinámico en la app de escritorio, con errores de arranque logueados y mostrados de forma clara al usuario.

**Principales riesgos:**
1. Sin backup automático de la base de datos real (riesgo de pérdida total de inventario ante cualquier incidente del equipo).
2. La app migra la base real automáticamente en cada apertura, sin backup previo.
3. `AutoLoginMiddleware` anula toda la autenticación — es una decisión de producto ya tomada y documentada en el propio código (no un descuido), pero de severidad crítica si no es la decisión vigente hoy.
4. El estado de Nota/Pedido se puede modificar libremente desde el formulario de edición normal, en paralelo a una máquina de transición de estados más estricta que además actualiza fechas de auditoría — dos caminos con reglas distintas para el mismo dato.
5. El único módulo de escalamiento de privilegios (`admin.py`, gestión de usuarios/roles) no tiene ningún test.

**Hallazgos por gravedad:** 1 crítica · 4 altas · 12 medias · 13 bajas = **30 hallazgos**.
**Hallazgos por estado de verificación:** 25 confirmados · 4 probables · 1 pendiente.

**Módulos revisados:** arquitectura general, modelo de datos completo (`models.py`, 992 líneas), capa de servicios (8 módulos), los 16 módulos de vistas, los 15 módulos de formularios, 55 migraciones, 64 templates, JS/CSS estático, seguridad y permisos, 1555 líneas de tests, build/empaquetado/CI, comandos de gestión.

**Módulos no revisados / revisados parcialmente:** ver sección 10 (Limitaciones).

**Las cinco acciones más importantes:**
1. Implementar backup automático de `db.sqlite3` (al menos antes de cada `migrate` automático en el arranque) — OPS-004 + OPS-002.
2. Confirmar explícitamente si `AutoLoginMiddleware` sigue siendo la política deseada, dado que ya se revirtió una vez por el mismo motivo — SEC-01.
3. Unificar el camino de cambio de `estado` de Nota/Pedido (formulario libre vs. máquina de transición) para que las fechas de auditoría no queden inconsistentes — API-01.
4. Agregar tests al módulo de administración de usuarios/roles — TEST-01.
5. Cerrar la ventana de condición de carrera en la verificación de stock antes de un egreso, una vez confirmado el modelo de concurrencia real de uso (ver pregunta pendiente) — STK-02.

---

## 2. Mapa del sistema

StockFlow es un **monolito Django 5.2** de una sola app (`inventario`), que se ejecuta de dos formas: como servidor web normal (`manage.py runserver`, para desarrollo) o como **aplicación de escritorio** nativa vía `pywebview` + `waitress` embebido, empaquetada a `.exe` con PyInstaller.

**Backend:** 16 módulos de vistas function-based (uno por entidad de dominio: artículos, tóner, PCs, impresoras, préstamos, reparaciones, intercambios, pedidos, notas, pendientes, patrimonios, movimientos, servicios, reportes, admin, core), todos protegidos de forma consistente con `@login_required`/`@require_POST`. Una capa `services/` (8 módulos) concentra lógica compartida sin modelo propio: búsqueda sin acentos, cálculo de stock, red/ping, listados con ordenamiento whitelist, historial de servicio.

**Modelo de datos:** gira en torno a un `Item` polimórfico (constraint "exactamente un FK" entre Toner/Articulo/ActivoPC/Impresora) que unifica todo lo que puede moverse en stock. El **stock nunca se persiste**: se recalcula siempre sumando `MovimientoDetalle` no anulados. Hay una capa secundaria de trazabilidad física individual (`PatrimonioUnidad`, con número único real a nivel de DB). El esquema es puramente de cantidades/trazabilidad, sin manejo de costos ni precios.

**Frontend:** Django Templates server-rendered, sin framework SPA ni build step — CSS/JS vanilla. Un sistema de diseño compartido (`ui.css`) y un combobox-buscador reutilizado (`searchable_select.js`) en la mayoría de los selects largos del sistema (en esta misma sesión se corrigió ahí un bug real de posicionamiento del panel desplegable).

**Persistencia:** SQLite único, vía Django ORM. La base real y la `SECRET_KEY` viven fuera del repo, en `%APPDATA%\StockToner\` de cada usuario/máquina — lo que implica que **cada instalación de escritorio tiene su propio inventario aislado**, sin sincronización entre PCs (ver pregunta pendiente en sección 9).

**Despliegue:** `build.ps1` genera el `.exe` vía PyInstaller a partir de un venv local; CI en GitHub Actions corre la suite de tests (no lint) en cada push/PR. Variables de entorno relevantes: `STOCKTONER_DEBUG` (fuerza DEBUG en el build empaquetado), `PYWEBVIEW_GUI` (fuerza motor Edge Chromium), `APPDATA` (ubicación de datos).

**Testing:** 169 tests (`manage.py test inventario`, confirmado corriendo dos veces en esta sesión y una tercera por el fork de rendimiento/testing: ~150-170s, en verde las tres veces), sobre una base SQLite efímera que Django crea y destruye solo — nunca toca la base real.

---

## 3. Hallazgos detallados

### A. Seguridad y permisos

#### SEC-01 — `AutoLoginMiddleware` anula toda la autenticación del sistema
- **Categoría:** Seguridad y permisos
- **Gravedad:** crítica
- **Estado de verificación:** confirmado
- **Archivo:** `inventario/middleware.py:1-22`; activado en `config/settings.py:62`
- **Explicación:** si nadie inició sesión, el middleware loguea automáticamente al primer superusuario que exista en la base. Es una decisión consciente y documentada en el propio código (fechada 2026-09-07, "de nuevo" — ya se había sacado antes por el mismo motivo), con instrucción explícita de cómo revertirla.
- **Escenario concreto:** `inventario/views/admin.py` protege cada vista con `@login_required` + `user_passes_test(is_superuser)`, un diseño de permisos correcto en sí mismo. Pero como el middleware ya autenticó al visitante como superusuario antes de llegar a la vista, ese chequeo siempre pasa — cualquiera que abra la app entra directo a gestión de usuarios/roles sin credenciales.
- **Impacto:** el sistema de permisos diferenciados es, en la práctica actual, inoperante como control de acceso real.
- **Evidencia:** `inventario/middleware.py:17-21`; `inventario/views/admin.py:12-16`.
- **Solución recomendada:** ninguna acción de código sin decisión previa — es una política de producto reversible con un paso documentado (sacar la línea de `MIDDLEWARE`). Lo que corresponde es la decisión explícita de si sigue siendo la política deseada hoy.
- **Riesgos de la solución:** si se saca sin avisar, rompe el flujo esperado de apertura directa sin login en un equipo de un solo usuario.
- **Prueba de verificación:** request anónimo a una URL de `admin.py` en un entorno de test con un superusuario creado → hoy entra sin loguearse; sin el middleware, debe redirigir a login.
- **Dependencias:** agrava a SEC-02 y a OPS-006.

#### SEC-02 — Combinación `DEBUG=True` + `ALLOWED_HOSTS` laxo si cambia el modo de despliegue
- **Categoría:** Seguridad y permisos
- **Gravedad:** media (hoy) / alta (condicional)
- **Estado de verificación:** probable
- **Archivo:** `config/settings.py:36-37`
- **Explicación:** `DEBUG=True` siempre que se corre como "app web normal" (tal como el propio README instruye para desarrollo). Con `DEBUG=True`, cualquier excepción no capturada muestra traceback completo, variables de entorno y SQL ejecutado. Hoy `ALLOWED_HOSTS=["127.0.0.1","localhost"]` limita el radio de exposición a loopback.
- **Escenario concreto:** si alguna vez se corre `runserver 0.0.0.0:8000` o se amplía `ALLOWED_HOSTS` para acceso en LAN sin cambiar `DEBUG`, combinado con SEC-01 (nadie necesita loguearse), cualquiera en esa red tendría acceso total y vería tracebacks completos ante cualquier error.
- **Impacto:** fuga de información interna si se da ese escenario de despliegue, que **hoy no está habilitado**.
- **Evidencia:** `config/settings.py:36`.
- **Solución recomendada:** ninguna acción requerida mientras el despliegue siga siendo loopback-only; dejarlo documentado como riesgo a vigilar si cambia el modelo de despliegue.
- **Riesgos:** ninguno si no se toca nada.
- **Prueba de verificación:** no aplica mientras `ALLOWED_HOSTS` siga restringido.
- **Dependencias:** SEC-01.

#### OPS-006 — `seed_demo` crea un superusuario con contraseña débil y pública (`demo`/`demo1234`)
- **Categoría:** Seguridad / operación
- **Gravedad:** media
- **Estado de verificación:** confirmado
- **Archivo:** `inventario/management/commands/seed_demo.py:140-151`; documentada en texto plano en `README.md`
- **Explicación:** si no existe ningún superusuario al correr `seed_demo`, se crea uno con usuario `demo` y contraseña hardcodeada `demo1234`, publicada en el README. El comando sí está bien guardado contra pisar datos reales (`if Pedido.objects.exists(): return`, verificado en código), pero no contra crear esta cuenta en una instalación que luego pasa a producción.
- **Escenario concreto:** alguien corre `seed_demo` para evaluar la app y esa instalación termina siendo la real de la organización; la cuenta `demo`/`demo1234` queda creada. Combinada con SEC-01, cualquiera que abra la app entra automáticamente como ese superusuario.
- **Impacto:** cuenta privilegiada con credencial trivial y pública.
- **Evidencia:** `seed_demo.py:145-147`; sección correspondiente del README.
- **Solución recomendada:** generar una contraseña aleatoria mostrada una sola vez por consola, o exigir cambio en el primer login — en vez de hardcodearla y publicarla.
- **Riesgos de la solución:** ninguno, es una cuenta de demo sin compatibilidad hacia atrás que proteger.
- **Prueba de verificación:** confirmar que no quede ninguna contraseña fija en código ni documentación.
- **Dependencias:** SEC-01.

---

### B. Backend y lógica de negocio

#### API-01 — El `estado` de Nota y Pedido se puede modificar libremente desde el formulario, evitando la máquina de transición y sus efectos de fecha
- **Categoría:** Backend / lógica de negocio
- **Gravedad:** alta
- **Estado de verificación:** confirmado
- **Archivo:** `inventario/forms/nota.py:18` (campo `"estado"` editable); `inventario/forms/pedidos.py:20` (ídem); máquina de transición en `inventario/views/notas.py` (`nota_avanzar`) y `inventario/views/pedidos.py:174-192` (`pedido_avanzar`, con side-effects de fecha en líneas 181-189)
- **Explicación:** hay dos caminos distintos para cambiar `estado`, con reglas distintas: (1) los botones "Avanzar" solo permiten mover al siguiente estado de un diccionario fijo, y en Pedido además setean `fecha_aprobado`/`fecha_recibido`/`fecha_entregado` según corresponda; (2) el formulario de edición normal trata `estado` como un campo común editable a cualquier valor del choices, sin pasar por el diccionario de transiciones ni setear esas fechas. El único control existente (`PedidoForm.clean()`) solo bloquea crear un pedido nuevo directamente como `ENTREGADO`, no restringe la edición de uno existente.
- **Escenario concreto:** alguien edita un Pedido en estado `HECHO` y cambia manualmente el desplegable "Estado" a `ENTREGADO` desde el formulario (no desde "Avanzar"). El guardado es válido, pero `fecha_entregado` queda `null` — el pedido figura como entregado sin fecha de entrega real.
- **Impacto:** inconsistencia de datos de auditoría en Pedido; los reportes que dependan de esas fechas (`reporte_pedidos_html/excel`) quedarían con datos incompletos para esos registros. En Nota el impacto es menor porque `Nota.save()` sí setea `fecha_cierre` automáticamente al detectar `FINALIZADA`, pero igual permite saltarse pasos intermedios del flujo.
- **Evidencia:** comparación entre `pedidos.py:181-189` (side-effects solo en `avanzar`) y la ausencia de esa lógica en el guardado estándar del formulario.
- **Solución recomendada:** decisión de producto, no autoejecutable — opciones: (a) sacar `estado` de los campos editables del formulario estándar, dejando el cambio solo vía botones de avance/cancelar; (b) si se necesita edición manual para corregir errores de carga, mover la lógica de fechas al `save()` del modelo para que sea consistente sin importar el camino de entrada.
- **Riesgos de la solución:** si hoy se depende de poder corregir el estado a mano desde el form, sacar el campo rompe ese flujo — confirmar con la usuaria si ese uso existe.
- **Prueba de verificación:** test que edite un Pedido `HECHO`→`ENTREGADO` vía `PedidoForm` y verifique si `fecha_entregado` queda `None` (hoy no existe ese test).
- **Dependencias:** relacionado con STK-03 (trazabilidad de movimientos).

---

### C. Inventario y reglas de stock

#### STK-02 — Ventana de condición de carrera en la verificación de stock antes de un egreso
- **Categoría:** Inventario y reglas de stock
- **Gravedad:** media
- **Estado de verificación:** probable (razonado desde el código y la semántica de SQLite/Django, no reproducido con concurrencia real)
- **Archivo:** `inventario/services/stock.py:46-56`; llamado desde `inventario/views/movimientos.py:74-86`, `inventario/views/toner.py:98-100`, `inventario/views/articulos.py:160-162`
- **Explicación:** el patrón en los 3 puntos de egreso es idéntico: dentro de un `transaction.atomic()`, se verifica el stock disponible (un SELECT agregado) y luego se crea el movimiento. En SQLite con transacciones diferidas (default de Django), el lock de escritura recién se toma en la primera escritura, no en el `BEGIN`. Dos requests casi simultáneos pueden leer el mismo stock "disponible" antes de que cualquiera escriba, y ambos pasar la validación aunque la suma exceda el stock real.
- **Escenario concreto:** stock de un tóner = 3. Dos usuarios piden entregar 2 y 3 casi al mismo tiempo; ambas lecturas ven "3 disponibles", ambas pasan la validación, ambas escriben su egreso. Resultado: stock final = -2, sin que ningún request haya visto error.
- **Impacto:** inconsistencia de stock bajo uso concurrente real — su probabilidad real depende de si el sistema se usa desde más de un puesto a la vez contra la misma base (ver pregunta pendiente en sección 9; si cada instalación es aislada de un solo usuario, este riesgo baja mucho).
- **Evidencia:** código citado; el propio test `test_toner_detail_marca_stock_negativo_como_inconsistente` confirma que el equipo ya contempló que el stock puede terminar negativo y construyó una marca visual para ese caso, en vez de una restricción que lo impida en origen.
- **Solución recomendada:** `select_for_update()` no es soportado de forma efectiva por SQLite; implementar un lock de aplicación (ej. una fila "semáforo" por ítem) o revalidar inmediatamente antes de la escritura final dentro del mismo bloque atómico. Evaluar costo/beneficio según la respuesta a la pregunta de concurrencia real de uso.
- **Riesgos de la solución:** complejidad adicional si el escenario de concurrencia real es raro en la práctica (instalación de escritorio, mayormente un usuario a la vez).
- **Prueba de verificación:** test con `threading`/`ThreadPoolExecutor` lanzando 2 egresos concurrentes contra el mismo ítem con stock justo al límite, verificando que solo uno tenga éxito.
- **Dependencias:** STK-03, TEST-03.

#### STK-03 — `Movimiento` no registra quién lo realizó
- **Categoría:** Inventario y reglas de stock
- **Gravedad:** media
- **Estado de verificación:** confirmado
- **Archivo:** `inventario/models.py:434-462`
- **Explicación:** a diferencia de `PatrimonioUnidad` (`asignado_por`) e `Intercambio` (`creado_por`, `resuelto_por`), `Movimiento` —el registro central de entradas/salidas de stock— no tiene ningún campo de usuario. `movimiento_anular` tampoco registra quién anuló.
- **Escenario concreto:** es imposible saber qué usuario entregó un tóner o anuló un movimiento a partir de los datos; esto es más relevante aún mientras SEC-01 siga activo.
- **Impacto:** trazabilidad incompleta en la entidad más sensible del sistema.
- **Evidencia:** `grep` de `settings.AUTH_USER_MODEL` en `models.py` solo aparece en `PatrimonioUnidad` e `Intercambio`.
- **Solución recomendada:** agregar `creado_por` (FK nullable a usuario) y `anulado_por`/`fecha_anulado` en `Movimiento`.
- **Riesgos de la solución:** migración aditiva de bajo riesgo (campo nullable); movimientos históricos quedarían en `NULL`, aceptable.
- **Prueba de verificación:** test que verifique que `movimiento_create`/`movimiento_anular` persisten `request.user`.
- **Dependencias:** relacionado con SEC-01.

#### STK-04 — Mecanismo de "combo" (`ItemComponente`/`Item.es_combo`) sin ninguna lógica de negocio implementada
- **Categoría:** Inventario y reglas de stock
- **Gravedad:** media
- **Estado de verificación:** confirmado
- **Archivo:** `inventario/models.py:359, 407-429`; único uso en `inventario/admin.py:38-39, 65`
- **Explicación:** el esquema permite armar un ítem "combo" compuesto por otros ítems (con constraints bien diseñadas a nivel de DB), pero ninguna vista, formulario o cálculo de stock lo usa — `stock_de_item()` no descompone un combo en sus componentes, no hay forma de cargarlo desde la UI principal (solo desde el admin de Django), y no hay tests.
- **Escenario concreto:** si alguien crea un combo desde el admin y lo entrega vía un egreso normal, el stock de sus componentes NO se descuenta — se comporta como un ítem independiente.
- **Impacto:** funcionalidad a medio camino — esquema completo, cero lógica de negocio. Riesgo si alguien empieza a usarlo desde el admin esperando que descuente componentes.
- **Evidencia:** `grep` de `es_combo`/`ItemComponente` en `views/`, `services/`, `forms/` sin resultados.
- **Solución recomendada:** **pregunta pendiente de negocio** — si sigue siendo deseada, completar la lógica (descomposición en `stock_de_item`/egreso, UI); si quedó abandonada, retirarla.
- **Riesgos de la solución:** completar es trabajo nuevo no trivial; retirar es una migración destructiva que requiere confirmar antes si hay combos ya cargados en la base real.
- **Prueba de verificación:** si se completa, test de egreso de un combo verificando descuento de cada componente.
- **Dependencias:** ninguna.

#### STK-05 — `hay_stock_suficiente()` es código muerto
- **Categoría:** Inventario y reglas de stock / deuda técnica
- **Gravedad:** baja
- **Estado de verificación:** confirmado
- **Archivo:** `inventario/services/stock.py:23-24`
- **Explicación:** sin ningún caller fuera de su propia definición y sus tests; `verificar_stock_suficiente` es la función efectivamente usada en los 3 flujos de egreso.
- **Escenario concreto:** confusión futura sobre cuál de las dos funciones es la "oficial".
- **Impacto:** bajo, solo mantenibilidad.
- **Evidencia:** `grep -rn "hay_stock_suficiente"` sin callers reales.
- **Solución recomendada:** eliminarla junto con sus tests dedicados, o documentar por qué se mantiene si tiene un propósito futuro.
- **Riesgos:** ninguno si se confirma que no se usa.
- **Prueba de verificación:** `manage.py test` en verde tras removerla.
- **Dependencias:** ninguna.

---

### D. Base de datos y persistencia

#### DB-01 — Sin restricción a nivel de base de datos para cantidades no positivas en `Movimiento`
- **Categoría:** Base de datos y persistencia
- **Gravedad:** media
- **Estado de verificación:** confirmado
- **Archivo:** `inventario/models.py:470` (`MovimientoDetalle.cantidad = IntegerField(validators=[MinValueValidator(1)])` — nótese que es `IntegerField`, no `PositiveIntegerField`)
- **Explicación:** `MinValueValidator` solo se ejecuta vía `full_clean()`/`ModelForm.is_valid()`. Cualquier `.objects.create()` o `.save()` directo (scripts, management commands, un form customizado futuro) puede persistir `cantidad <= 0` sin que SQLite lo impida — no hay `CheckConstraint` en `Meta.constraints`.
- **Escenario concreto:** ya demostrado en la práctica — el propio test `test_toner_detail_marca_stock_negativo_como_inconsistente` crea un `MovimientoDetalle` "sin pasar por la validación" para simular exactamente este caso, con un comentario que sugiere que ya pasó de verdad ("stock negativo histórico, de antes de la validación").
- **Impacto:** la integridad de una regla central depende por completo de que todo código futuro pase por el formulario correcto.
- **Evidencia:** ausencia de `CheckConstraint` en `Meta` del modelo; comentario del test citado.
- **Solución recomendada:** agregar `CheckConstraint(check=Q(cantidad__gt=0), ...)`.
- **Riesgos de la solución:** **si existen filas históricas con `cantidad<=0` en la base real, la migración fallaría al aplicarse hasta limpiar esos datos** — debe verificarse contra la base real antes de aplicar, fuera del alcance de esta auditoría de solo lectura.
- **Prueba de verificación:** tras limpiar datos históricos si los hay, test que confirme `IntegrityError` al crear `cantidad=0` directo vía ORM.
- **Dependencias:** condicionado por la pregunta pendiente #3 de la sección 9.

#### DB-02 — Migración `0029_refactor_prestamo_pendiente.py` eliminó columnas sin backfill
- **Categoría:** Base de datos y persistencia
- **Gravedad:** baja (histórico, no accionable retroactivamente)
- **Estado de verificación:** confirmado como patrón; impacto real no verificable sin acceder a la base real
- **Archivo:** `inventario/migrations/0029_refactor_prestamo_pendiente.py:46-50`
- **Explicación:** la migración migra correctamente `Pendiente.completado`→`Pendiente.estado` con `RunPython` (con reversa incluida), pero inmediatamente elimina 5 columnas (`Prestamo.proyector`, `.camara_web`, `.prolongacion`, `.notebook`, `Item.categoria_prestamo`) sin ningún `RunPython` previo que las migre al nuevo esquema.
- **Impacto:** si esos campos tenían datos reales al momento de esa migración (no verificable aquí), se perdieron silenciosamente. Es una lección de proceso, no algo corregible hoy.
- **Evidencia:** contraste con la migración `0043_remove_pedido_servicio_solicitante_pedido_servicios.py`, que sí hace `AddField → RunPython de backfill con reversa → RemoveField` correctamente — 0029 es la excepción, no la norma.
- **Solución recomendada:** checklist de proceso para migraciones futuras: ¿hace falta backfill antes de cualquier `RemoveField`?
- **Riesgos:** ninguno (es solo recomendación de proceso).
- **Prueba de verificación:** no aplica.
- **Dependencias:** ninguna.

---

### E. Rendimiento y escalabilidad

#### PERF-01 — Sin índice en los campos más filtrados/ordenados de `Movimiento`
- **Categoría:** Rendimiento
- **Gravedad:** media
- **Estado de verificación:** confirmado (ausencia de índice) / probable (impacto real, no medido con volumen real)
- **Archivo:** `inventario/models.py:445-459`
- **Explicación:** `fecha`, `anulado` y `tipo` no tienen `db_index=True` ni `Meta.indexes` — solo `ordering=["-fecha"]`. Son el filtro/orden principal en listados, reportes y el historial de servicio.
- **Escenario concreto:** con años de movimientos acumulados, cada `order_by("-fecha")` y `filter(anulado=False)` hace un full table scan.
- **Impacto:** degradación progresiva no medible hoy sin el volumen real de datos (no se puede tocar la base real en esta auditoría).
- **Evidencia:** `Meta` del modelo sin `indexes=[...]`.
- **Solución recomendada:** `models.Index(fields=["-fecha"])` y `models.Index(fields=["anulado", "fecha"])` vía migración `AddIndex` (no destructiva).
- **Riesgos de la solución:** ninguno relevante; migración de índice en SQLite es segura.
- **Prueba de verificación:** medir con `EXPLAIN QUERY PLAN` antes/después sobre una copia de la base real con volumen representativo (nunca sobre la real en vivo).
- **Dependencias:** ninguna.

#### PERF-02 — Reportes sin filtro de mes cargan el historial completo sin límite
- **Categoría:** Rendimiento
- **Gravedad:** baja
- **Estado de verificación:** confirmado (código) / probable (impacto)
- **Archivo:** `inventario/views/reportes.py:287-298` (patrón repetido en los demás `reporte_*`)
- **Explicación:** si no se especifica mes, el queryset no filtra por fecha y recorre todo el historial.
- **Escenario concreto:** usuario abre un reporte sin elegir mes en una instalación con años de datos.
- **Impacto:** bajo en la práctica dado el volumen típico esperado de este sistema (inventario de una organización, no datos masivos).
- **Evidencia:** ausencia de `.filter()` por fecha cuando no se especifica mes.
- **Solución recomendada:** acotar a un rango por default (ej. últimos 12 meses) o exigir selección de período — decisión de producto, no solo técnica.
- **Riesgos:** cambiar el comportamiento por defecto puede sorprender a quien hoy espera ver "todo" sin filtro.
- **Prueba de verificación:** test que mida cantidad de queries/tiempo con dataset grande sintético en DB de test.
- **Dependencias:** ninguna.

---

### F. Testing y calidad

#### TEST-01 — El módulo de administración de usuarios/roles no tiene ningún test
- **Categoría:** Testing
- **Gravedad:** alta
- **Estado de verificación:** confirmado
- **Archivo:** `inventario/views/admin.py` (9 vistas); `inventario/tests.py` completo
- **Explicación:** las 9 vistas de `admin.py` están correctamente protegidas con `@login_required` + `@solo_superadmin`, pero no hay ni un solo test que verifique que un usuario no-superadmin es rechazado, ni que las operaciones de alta/baja/edición de usuarios y roles funcionan.
- **Escenario concreto:** alguien quita por error el decorador al refactorizar algo relacionado, y nada lo detecta hasta que un usuario no-admin accede a gestión de cuentas en producción.
- **Impacto:** escalamiento de privilegios no detectado por CI si se introduce accidentalmente.
- **Evidencia:** `grep` de `admin_usuarios|admin_panel|solo_superadmin|is_superuser=False` en `tests.py` sin resultados.
- **Solución recomendada:** clase de test que cubra (a) usuario no-superadmin recibe redirect/403 en las 9 rutas, (b) las operaciones CRUD funcionan con superadmin.
- **Riesgos:** ninguno, puramente aditivo.
- **Prueba de verificación:** la clase de test nueva en sí.
- **Dependencias:** relacionado con SEC-01 (mismo módulo, otro ángulo).

#### TEST-02 — ~16% de la suite son smoke tests que solo verifican HTTP 200
- **Categoría:** Testing
- **Gravedad:** media
- **Estado de verificación:** confirmado
- **Archivo:** `inventario/tests.py:289-298` (`ViewsSmokeTest._get_ok`), 27 usos en todo el archivo
- **Explicación:** `_get_ok` solo hace `assertEqual(status_code, 200)`. Es una decisión transparente (la clase se llama explícitamente "Smoke"), no cobertura real disfrazada, pero deja sin verificar contenido/estado en esas 27 rutas.
- **Escenario concreto:** una vista rota que sigue devolviendo 200 con datos incorrectos no sería detectada.
- **Impacto:** medio — bajo porque conviven con clases que sí assertean estado real (`VistasCrudTest`, etc.).
- **Evidencia:** definición de `_get_ok`; 27 llamados.
- **Solución recomendada:** no reemplazar todos; priorizar agregar asserts de contenido en las rutas más críticas (altas de stock, reportes).
- **Riesgos:** ninguno.
- **Prueba de verificación:** ampliar 3-5 de los `_get_ok` más críticos y confirmar que siguen en verde.
- **Dependencias:** ninguna.

#### TEST-03 — Sin test de condición de carrera/concurrencia real sobre stock
- **Categoría:** Testing
- **Gravedad:** media
- **Estado de verificación:** pendiente
- **Archivo:** N/A (ausencia transversal)
- **Explicación:** hay buenos tests de borde de stock (no permite egreso sin stock, no permite doble reserva), pero ninguno simula dos requests verdaderamente concurrentes.
- **Escenario concreto:** dos usuarios confirman una entrega del mismo ítem casi al mismo tiempo.
- **Impacto:** condicionado por STK-02 y por la respuesta a la pregunta de concurrencia real de uso.
- **Evidencia:** ausencia de `TransactionTestCase`/`threading` en `tests.py`.
- **Solución recomendada:** no construir este test hasta confirmar que STK-02 es un riesgo real dado el modelo de uso (ver sección 9); si se confirma, un `TransactionTestCase` con dos threads.
- **Riesgos:** los tests de concurrencia son frágiles y lentos si se abusa — usar con moderación.
- **Prueba de verificación:** la que se diseñe, condicionada a STK-02.
- **Dependencias:** STK-02.

#### TEST-04 — Import sin uso en `views/impresoras.py`
- **Categoría:** Testing/calidad (detectado vía `ruff`)
- **Gravedad:** baja
- **Estado de verificación:** confirmado
- **Archivo:** `inventario/views/impresoras.py:1` (`import csv` sin usar)
- **Explicación:** detectado por `ruff check --statistics` (regla F401).
- **Impacto:** ninguno funcional, solo ruido.
- **Evidencia:** salida de `ruff check inventario/`.
- **Solución recomendada:** quitar el import.
- **Riesgos:** ninguno.
- **Prueba de verificación:** `ruff check` limpio sobre ese archivo.
- **Dependencias:** ninguna.

#### TEST-05 — El patrón de test de regresión N+1 no cubre todas las vistas con prefetch
- **Categoría:** Testing/Rendimiento
- **Gravedad:** baja
- **Estado de verificación:** confirmado
- **Archivo:** `inventario/tests.py:1385-1429` (`SinNMasUnoTest`, aplicado hoy solo a `/impresoras/` y `/pendientes/`)
- **Explicación:** existe un patrón sólido (`CaptureQueriesContext` + assert de que el conteo de queries no escala), pero no está extendido a `movimientos_list`, `prestamos_list` ni `pedido_detail` — que hoy SÍ están bien hechos (verificado manualmente), pero sin ningún test que lo proteja de una futura regresión.
- **Impacto:** si alguien quita un `prefetch_related` sin querer en esas vistas, nada lo detecta.
- **Evidencia:** alcance actual de `SinNMasUnoTest` vs. trazado manual de las 3 vistas mencionadas.
- **Solución recomendada:** extender la clase a esas 3 vistas.
- **Riesgos:** ninguno, aditivo.
- **Prueba de verificación:** los tests nuevos en sí.
- **Dependencias:** ninguna.

---

### G. Frontend, interfaz y experiencia de usuario

#### FE-01 — Ningún formulario de alta/edición previene el doble-submit
- **Categoría:** Frontend / UX
- **Gravedad:** media
- **Estado de verificación:** confirmado
- **Archivo:** todo el árbol `inventario/templates/inventario/**/form.html`; confirmado por ausencia de `disabled` en botones de submit (el único uso de `disabled` en todo el proyecto es el botón de ping AJAX en `base.html:356,377`)
- **Explicación:** en ningún formulario de creación/edición (pedidos, notas, artículos, tóner, PCs, impresoras, préstamos, reparaciones, movimientos, patrimonios) el botón "Guardar" se deshabilita al enviar, ni hay guardas JS contra reenvío.
- **Escenario concreto:** usuario con conexión lenta hace doble click en "Guardar"; ambos POST llegan al servidor antes de que la primera respuesta redirija la página.
- **Impacto:** riesgo de registros duplicados (pedidos, movimientos de stock, préstamos) si el backend no es idempotente ante ese escenario — el impacto real depende de los constraints de unicidad existentes.
- **Evidencia:** `grep` de `disabled` en templates y JS, sin resultados en botones de submit de formularios de escritura.
- **Solución recomendada:** deshabilitar el botón de submit (con estado de carga) en el evento `submit`, de forma genérica y delegada desde `base.html` para no tocar cada template.
- **Riesgos de la solución:** cuidado de no deshabilitar antes de que el navegador dispare la validación HTML5 nativa (podría bloquear la corrección de errores).
- **Prueba de verificación:** doble-click rápido en un formulario de creación → debe crearse un solo registro.
- **Dependencias:** relacionado con los constraints de unicidad de los hallazgos de base de datos.

#### FE-03 — Doble asociación de `<label>` en el checkbox "Es patrimonial"
- **Categoría:** Frontend / accesibilidad
- **Gravedad:** baja
- **Estado de verificación:** confirmado
- **Archivo:** `inventario/templates/inventario/articulos/articulo_form.html:41`
- **Explicación:** el checkbox tiene un `<label for="id_es_patrimonial">` explícito Y, en la misma línea, un segundo `<label>` que envuelve implícitamente el mismo checkbox. Es el único caso así detectado (el campo "Activo" en la línea siguiente usa el patrón correcto).
- **Escenario concreto:** un lector de pantalla puede anunciar el nombre accesible del checkbox de forma duplicada o inconsistente.
- **Impacto:** contradice parcialmente la afirmación del README de "0 violaciones axe-core" en ese control puntual.
- **Evidencia:** línea 41 completa citada en el reporte del fork de frontend.
- **Solución recomendada:** quitar el `for=` del primer label (convertirlo en `<span>`) o quitar el anidamiento del segundo, dejando una sola asociación.
- **Riesgos:** ninguno, cambio de 1 línea sin lógica involucrada.
- **Prueba de verificación:** correr axe-core sobre esa pantalla específica y confirmar 0 violaciones de la regla de labels.
- **Dependencias:** ninguna.

#### FE-04 — El listado de Pendientes es el único sin paginación
- **Categoría:** Frontend / consistencia
- **Gravedad:** baja (hoy), potencialmente media si crece el volumen
- **Estado de verificación:** confirmado
- **Archivo:** `inventario/views/pendientes.py:19-45` (`pendientes_page`)
- **Explicación:** los otros 12 listados del sistema usan `Paginator`; `pendientes_page` trae todos los `Pendiente` sin límite.
- **Escenario concreto:** con cientos/miles de pendientes acumulados, la pantalla carga y renderiza todos de una vez.
- **Impacto:** UX inconsistente respecto al resto del sistema; rendimiento de renderizado degradándose con el tiempo si no se depuran pendientes completados/cancelados.
- **Evidencia:** `pendientes.py` es el único archivo de `views/*.py` sin `Paginator`.
- **Solución recomendada:** aplicar `Paginator` igual que en el resto de los listados.
- **Riesgos de la solución:** verificar antes que el template no dependa de iterar "todos" para algún contador total que se rompería al paginar.
- **Prueba de verificación:** cargar más de una página de pendientes de prueba y confirmar que la paginación funciona igual que en Notas/Pedidos.
- **Dependencias:** ninguna.

---

### H. Arquitectura, duplicaciones y deuda técnica

#### DUP-01 — Cuatro implementaciones independientes de "agregar fila a un formset dinámicamente"
- **Categoría:** Arquitectura / duplicaciones (detectado de forma independiente por dos forks: arquitectura y frontend)
- **Gravedad:** media
- **Estado de verificación:** confirmado
- **Archivos:** `movimientos/movimiento_form.html:228` (`addFormRow`, parametrizada), `notas/form.html:167` (`agregarFilaNota`), `pedidos/form.html:145` (`addDetallePedido`, clona DOM), `pedidos/detail.html:343` (`addDetalle`)
- **Explicación:** las cuatro resuelven el mismo problema (incrementar `TOTAL_FORMS` de un formset Django y agregar una fila al DOM) con tres estrategias de implementación distintas, sin ningún helper compartido.
- **Escenario concreto:** el bug de posicionamiento ya corregido esta sesión en `searchable_select.js` se propagó automáticamente a los 4 templates porque ESE archivo sí está centralizado; un bug equivalente en la lógica de "agregar fila" (ej. un off-by-one en el índice) habría que corregirlo 4 veces por separado, con riesgo de olvidar una.
- **Impacto:** mantenibilidad — no es un bug activo hoy, es deuda técnica con un patrón de riesgo ya demostrado en este mismo repo.
- **Evidencia:** las 4 funciones citadas, mismo propósito, lógica de reemplazo de índices casi idéntica.
- **Solución recomendada:** extraer un helper único a `static/inventario/formset_rows.js`, parametrizable, y migrar los 4 templates — no urgente.
- **Riesgos de la solución:** el de `pedidos/form.html` usa clonado de DOM que preserva el wrapper del buscador con lógica especial de desarmado; migrarlo a un patrón distinto requiere prueba manual en navegador (no hay tests automatizados de JS en este repo).
- **Prueba de verificación:** prueba manual de los 4 formularios tras la unificación, verificando que el buscador siga funcionando en filas nuevas.
- **Dependencias:** ninguna.

#### ARQ-01 — `forms/__init__.py` es un barrel incompleto y mayormente sin usar
- **Categoría:** Arquitectura
- **Gravedad:** baja
- **Estado de verificación:** confirmado
- **Archivo:** `inventario/forms/__init__.py:1-41`
- **Explicación:** el paquete tiene 15 módulos, pero el barrel solo re-exporta símbolos de 13 (faltan `patrimonios.py` y `admin_forms.py`). Solo `views/movimientos.py` importa a través del barrel; el resto importa directo del submódulo. Línea 24 tiene un comentario placeholder sin limpiar (`# ajustá a tus nombres reales`).
- **Escenario concreto:** alguien agrega un form nuevo a `forms/patrimonios.py` asumiendo que el barrel funciona para ese módulo (como sí funciona para otros) y se encuentra con un `ImportError`.
- **Impacto:** bajo — solo mantenibilidad/confusión; no afecta el comportamiento actual.
- **Evidencia:** contraste entre `forms/__init__.py:23-24` y los imports directos en `views/patrimonios.py:9-10`, `views/admin.py:9`.
- **Solución recomendada:** elegir un único patrón — eliminar el barrel (consistente con el 94% del código que ya importa directo) o completarlo con los 2 módulos faltantes y migrar todo a usarlo.
- **Riesgos de la solución:** ninguno funcional si se hace con cuidado; mitigable corriendo `check` + suite de tests tras el cambio.
- **Prueba de verificación:** `manage.py check` + `manage.py test inventario` sin `ImportError`.
- **Dependencias:** ninguna.

#### ARQ-03 — `diagrama_app.html` huérfano en la raíz del repo
- **Categoría:** Arquitectura / documentación
- **Gravedad:** baja
- **Estado de verificación:** confirmado
- **Archivo:** `diagrama_app.html` (raíz, 23KB, trackeado en git)
- **Explicación:** diagrama de arquitectura standalone no enlazado desde README ni desde `docs/`. Sin ninguna referencia en todo el código/docs.
- **Escenario concreto:** queda desactualizado sin que nadie lo note (por ejemplo, no reflejará los campos `pedidos_relacionados`/`notas_relacionadas` agregados en esta misma sesión).
- **Impacto:** bajo — riesgo de que alguien lo abra confiando en que está actualizado.
- **Evidencia:** `grep` de `"diagrama_app"` en todo el repo sin resultados.
- **Solución recomendada:** moverlo a `docs/` y enlazarlo desde el README, o eliminarlo si `modelo-de-datos.pdf` ya cumple ese rol — decisión del equipo.
- **Riesgos:** ninguno.
- **Prueba de verificación:** no aplica.
- **Dependencias:** ninguna.

#### ARQ-04 — README documenta "121 tests"; la suite real tiene 169
- **Categoría:** Arquitectura / documentación
- **Gravedad:** baja
- **Estado de verificación:** confirmado
- **Archivo:** `README.md` (dos menciones), contra `inventario/tests.py` (169 confirmado por 3 corridas independientes en esta auditoría)
- **Explicación:** el número quedó desactualizado a medida que se agregaron tests.
- **Impacto:** bajo, cosmético — relevante porque el README menciona que el proyecto se está transformando para portfolio.
- **Evidencia:** conteo real 169 vs. texto del README.
- **Solución recomendada:** actualizar "121"→"169" en ambos lugares.
- **Riesgos:** ninguno.
- **Prueba de verificación:** ninguna, cambio de texto.
- **Dependencias:** ninguna.

#### ARQ-05 — El admin de Django no registra los modelos transaccionales centrales
- **Categoría:** Arquitectura (informativo — requiere decisión funcional, no es claramente un defecto)
- **Gravedad:** baja
- **Estado de verificación:** confirmado como hecho; probable como "problema" (depende de la intención)
- **Archivo:** `inventario/admin.py` — registra 9 modelos de catálogo base; no registra `Pedido`, `Nota`, `Reparacion`, `PatrimonioUnidad`, `ActivoPC`, `AsignacionImpresora`, entre otros.
- **Explicación:** el README dice "panel de administración para gestión avanzada" sin aclarar que cubre solo catálogos base, no las entidades transaccionales con UI propia dedicada.
- **Escenario concreto:** si la UI custom de Pedido/Nota/Reparación falla, no hay vía de emergencia por `/admin/` — habría que usar `shell` directo contra la base real.
- **Impacto:** bajo en uso normal; medio como plan de contingencia ante un bug en la UI custom.
- **Evidencia:** `grep` de registros en `admin.py`.
- **Solución recomendada:** **pregunta pendiente** — ¿se quiere admin de Django como respaldo, o es decisión consciente de que todo pase por la UI custom? Es razonable de cualquier forma (muchos proyectos excluyen del admin entidades con lógica compleja en `save()` para no bypasearla).
- **Riesgos de agregar:** el admin de Django bypasea validaciones de `Form.clean()` a medida (aunque sí dispara `Model.save()`).
- **Prueba de verificación:** si se agrega, probar manualmente que no deja estados inconsistentes.
- **Dependencias:** ninguna.

---

### I. Despliegue, mantenimiento y recuperación

#### OPS-002 — La app migra la base real automáticamente en cada arranque, sin backup previo
- **Categoría:** Despliegue / recuperación
- **Gravedad:** alta
- **Estado de verificación:** confirmado
- **Archivo:** `desktop_app.py:236-246` (`call_command("migrate", "--run-syncdb", verbosity=0)`)
- **Explicación:** cada vez que se abre la app de escritorio, se aplican automáticamente todas las migraciones pendientes contra `%APPDATA%\StockToner\db.sqlite3`, en silencio y sin ningún backup automático previo.
- **Escenario concreto:** se publica una nueva versión del `.exe` con una migración con un bug; el usuario abre la nueva versión, la migración corre sola, falla o corrompe datos a mitad de camino, sin ningún respaldo tomado un segundo antes.
- **Impacto:** pérdida o corrupción de datos reales sin rollback automático posible.
- **Evidencia:** línea 246 citada; ausencia total de lógica de backup (ver OPS-004).
- **Solución recomendada:** copiar `db.sqlite3` con timestamp a una carpeta de backups local (rotando los últimos N) antes de migrar.
- **Riesgos de la solución:** mínimo — copiar un SQLite de pocos MB agrega una fracción de segundo; cuidar no copiar mientras el archivo está en un estado inconsistente (journal/WAL abierto).
- **Prueba de verificación:** verificar que se genere el backup antes de aplicar migraciones nuevas; simular una migración fallida y confirmar que el backup previo permite restaurar.
- **Dependencias:** OPS-004; su severidad sube si el fork de base de datos confirma una migración concreta de riesgo (ver DB-02).

#### OPS-004 — No existe ningún mecanismo de backup automático de la base de datos
- **Categoría:** Despliegue / recuperación ante desastres
- **Gravedad:** alta
- **Estado de verificación:** confirmado
- **Archivo:** N/A — `grep` de `"backups"` en todo el código Python del repo sin coincidencias
- **Explicación:** existe una carpeta `backups/` en la raíz (gitignoreada, local), pero ningún archivo del proyecto escribe nada ahí ni en ningún otro lado — en el mejor de los casos, un lugar para copias manuales.
- **Escenario concreto:** se reinstala Windows, se pierde el perfil de usuario, el disco falla, o se desinstala la app sin saber que `%APPDATA%\StockToner\db.sqlite3` contiene todo el inventario real.
- **Impacto:** pérdida total de datos de inventario ante cualquier incidente del equipo, sin ningún mecanismo de recuperación propio.
- **Evidencia:** búsqueda exhaustiva de "backups" en todo el código: cero resultados.
- **Solución recomendada:** backup automático al cerrar la app (o periódico), con timestamp y rotación (ej. últimos 10-15). Complementa a OPS-002.
- **Riesgos de la solución:** consumo de espacio si no se rota bien; evitar copiar mientras SQLite tiene escrituras en vuelo.
- **Prueba de verificación:** verificar generación/rotación de backups y que un backup restaurado manualmente deje la app funcional.
- **Dependencias:** OPS-002.

#### OPS-001 — `build.ps1` repite, en `collectstatic`, el mismo patrón de fallo silencioso ya corregido para PyInstaller
- **Categoría:** Despliegue
- **Gravedad:** media
- **Estado de verificación:** confirmado
- **Archivo:** `build.ps1:28-30`
- **Explicación:** el commit más reciente del repo corrigió un fallo silencioso de PyInstaller agregando verificación de `$LASTEXITCODE`. El paso de `collectstatic` sigue redirigiendo toda la salida a `Out-Null` sin verificar el código de salida — `$ErrorActionPreference="Stop"` no cubre códigos de salida de ejecutables externos como `python.exe`, solo errores de cmdlets.
- **Escenario concreto:** si `collectstatic` falla, el script sigue de largo, compila igual con PyInstaller y reporta "Build completado con éxito" con estáticos desactualizados o incompletos empaquetados.
- **Impacto:** se distribuye un ejecutable con CSS/JS rotos sin que quien hace el build se entere.
- **Evidencia:** `git show` del commit más reciente muestra que el chequeo se agregó solo alrededor de PyInstaller, no de collectstatic.
- **Solución recomendada:** mismo patrón que ya se usa para PyInstaller — quitar el `Out-Null` (o redirigir a log) y verificar `$LASTEXITCODE`.
- **Riesgos de la solución:** ninguno, cambio aislado en script de build.
- **Prueba de verificación:** forzar un fallo de collectstatic y confirmar que el script aborta.
- **Dependencias:** ninguna.

#### OPS-003 — `convert_movimientos.py` es código muerto
- **Categoría:** Despliegue / mantenimiento
- **Gravedad:** baja
- **Estado de verificación:** confirmado
- **Archivo:** `inventario/management/commands/convert_movimientos.py:15-24`
- **Explicación:** el comando referencia campos (`toner`, `cantidad`) que ya no existen en el modelo `Movimiento` actual — la condición nunca es verdadera, el comando es un no-op seguro en el esquema actual.
- **Escenario concreto:** alguien lo ejecuta pensando que convierte datos y no pasa nada, generando confusión sobre si la migración ya se hizo.
- **Impacto:** ninguno funcional hoy; deuda técnica que confunde.
- **Evidencia:** comparación entre el comando y la definición actual de `Movimiento`.
- **Solución recomendada:** eliminarlo (la migración de datos que resolvía ya se hizo) o dejarlo con una guarda explícita de "comando histórico no aplicable".
- **Riesgos:** ninguno si se confirma que no hay bases "viejas" que dependan de él (dado que ya es un no-op, no debería haberlas).
- **Prueba de verificación:** `manage.py test` en verde tras removerlo.
- **Dependencias:** se superpone con el alcance de duplicaciones/deuda técnica — no es el mismo hallazgo que DUP-01.

#### OPS-005 — El CI no corre `ruff` pese a tener configuración
- **Categoría:** Despliegue / CI
- **Gravedad:** baja
- **Estado de verificación:** confirmado
- **Archivo:** `.github/workflows/tests.yml:9-24`
- **Explicación:** el único job instala dependencias y corre `manage.py test`; no hay ningún paso de lint, pese a existir `ruff.toml` en la raíz y commits históricos de "limpia lint".
- **Escenario concreto:** un PR introduce violaciones de lint y el CI lo deja pasar en verde.
- **Impacto:** drift de calidad de código no detectado automáticamente.
- **Evidencia:** contenido completo de `tests.yml` vs. existencia de `ruff.toml`.
- **Solución recomendada:** agregar un step `ruff check .`.
- **Riesgos de la solución:** si hay violaciones ya acumuladas, el primer CI con esta regla fallaría — correr `ruff check` localmente primero (confirmado en esta auditoría: 31 violaciones hoy, 30 de línea larga + 1 import sin uso, ver TEST-04) antes de hacerlo bloqueante.
- **Prueba de verificación:** el nuevo step debe fallar ante una violación introducida a propósito en una rama de prueba.
- **Dependencias:** TEST-04.

---

## 4. Inconsistencias entre módulos

| Inconsistencia | Módulos involucrados | Hallazgo relacionado |
|---|---|---|
| El `estado` de Nota/Pedido tiene dos caminos de cambio con reglas distintas (formulario libre vs. máquina de transición con side-effects de fecha) | `forms/nota.py`, `forms/pedidos.py` vs. `views/notas.py`, `views/pedidos.py` | API-01 |
| README afirma "121 tests"; la suite real tiene 169 | `README.md` vs. `tests.py` | ARQ-04 |
| README afirma accesibilidad "0 violaciones axe-core"; se encontró un caso real de doble-label | `README.md` vs. `articulo_form.html` | FE-03 |
| README afirma panel de administración "para gestión avanzada"; en la práctica cubre solo 9 de ~20 modelos (los de catálogo, no los transaccionales) | `README.md` vs. `admin.py` | ARQ-05 |
| El combo (`ItemComponente`) existe completo en el modelo de datos pero no en ninguna vista/servicio/formulario | `models.py` vs. `views/`, `services/`, `forms/` | STK-04 |
| 12 de 13 listados paginan; Pendientes no | `views/*.py` | FE-04 |
| La mayoría de migraciones hacen backfill antes de eliminar columnas; la migración 0029 no | `migrations/0029...` vs. `migrations/0043...` | DB-02 |
| El build corrige fallos silenciosos en el paso de PyInstaller pero no en el de `collectstatic`, inmediatamente anterior en el mismo script | `build.ps1` | OPS-001 |

---

## 5. Duplicaciones y deuda técnica

**Conviene unificar:**
- **DUP-01** (4 implementaciones de "agregar fila a formset"): sí conviene, con prioridad baja — el beneficio es evitar corregir el mismo tipo de bug 4 veces, como ya pasó (en otro archivo) con `searchable_select.js` esta sesión. No es urgente porque hoy no hay un bug activo ahí.

**Conviene retirar (si se confirma que no se usan):**
- **STK-05** (`hay_stock_suficiente()`): sin caller real, candidata directa a eliminar.
- **OPS-003** (`convert_movimientos.py`): no-op en el esquema actual, candidato a eliminar.
- **ARQ-03** (`diagrama_app.html`): huérfano, mover a `docs/` o eliminar.

**Conviene mantener tal como está (evaluado y descartado como problema):**
- **DB-03** (sin `UniqueConstraint` en la IP de `Impresora`): es una decisión documentada y deliberada en el propio código, con plan explícito de cuándo promoverla — no es deuda técnica, es una decisión de transición bien gestionada.
- La ausencia de un helper único para búsqueda/filtrado en `services/busqueda.py` no mostró duplicación real de lógica equivalente entre vistas — la capa de servicios está bien delimitada.

**Requiere decisión de negocio antes de poder clasificarse (no es puramente técnico):**
- **STK-04** (combo): completar o retirar, no se puede decidir solo desde el código.
- **ARQ-05** (admin de Django incompleto): mantener acotado a catálogos o ampliar a transaccionales, es una decisión de producto.

---

## 6. Pruebas y cobertura

**Lo que se pudo ejecutar realmente (confirmado, no inferido):**
- `python manage.py test inventario` — corrido 3 veces de forma independiente durante esta sesión (dos veces en el trabajo de desarrollo previo a la auditoría, una vez más por el fork de rendimiento/testing): **169 tests, 0 fallos, ~150-170s cada corrida**, sobre una base SQLite efímera que Django crea y destruye solo.
- `python manage.py check` — sin problemas, corrido en varios momentos de la sesión.
- `ruff check inventario/ --no-fix --statistics` — **31 violaciones**: 30 `E501` (línea larga, cosmético) + 1 `F401` (import sin uso, TEST-04). No se aplicó `--fix` ni se modificó nada.

**Lo que NO se pudo ejecutar en esta auditoría (y por qué):**
- Cualquier prueba contra la base de datos real (`%APPDATA%\StockToner\db.sqlite3`) — prohibido explícitamente por las reglas de esta auditoría. Esto deja sin confirmar: si existen datos históricos con `cantidad<=0` (condiciona DB-01), el volumen real de `Movimiento` (condiciona la urgencia real de PERF-01), y si hay combos (`ItemComponente`) ya cargados (condiciona el riesgo de retirar STK-04).
- Testing visual en navegador (solo se hizo revisión estática de templates/JS/CSS) — no se relanzó el servidor de desarrollo durante la fase de auditoría para no entrar en conflicto con la restricción de "no reiniciar servicios"; el hallazgo FE-03 está confirmado por lectura de HTML generado, pero no se corrió axe-core sobre él como hace el propio equipo según el README.
- Pruebas de concurrencia real (dos requests simultáneos) — no se simuló tráfico concurrente contra ninguna base, ni siquiera la de test, en esta etapa de solo lectura.
- `pip-audit`/`safety` sobre `requirements.txt` — no se instaló ninguna herramienta nueva, por restricción explícita de la auditoría.

**Escenarios de test concretos que faltan, priorizados:**
1. Permisos del módulo admin (TEST-01) — prioridad alta, es el único punto de escalamiento de privilegios sin cobertura.
2. Cambio de `estado` de Pedido vía formulario estándar saltándose la máquina de transición (relacionado a API-01) — confirma o descarta el hallazgo con un test reproducible.
3. Concurrencia de egreso de stock (TEST-03/STK-02) — condicionado a confirmar el modelo de uso real primero.
4. `CheckConstraint` de cantidad positiva en `Movimiento` (DB-01) — una vez limpiados los datos históricos si los hubiera.

---

## 7. Plan de corrección priorizado

### P0 — Urgente

**Estado: resuelto el 2026-10-23** (ver nota de actualización al inicio del documento).

| Acción | Esfuerzo | Dependencias | Riesgo | Criterio de aceptación | Estado |
|---|---|---|---|---|---|
| Implementar backup automático de `db.sqlite3` (OPS-004) | Medio (1-2 días) | Ninguna | Bajo | Al cerrar/abrir la app se genera un backup con timestamp, rotado, restaurable manualmente | ✅ `inventario/services/backups.py` + 3 tests |
| Backup previo a la migración automática en el arranque (OPS-002) | Bajo (medio día, reutiliza OPS-004) | OPS-004 | Bajo | Existe un backup fechado inmediatamente antes de cada `migrate` automático | ✅ `desktop_app.py::setup_django()` |
| Confirmar explícitamente si `AutoLoginMiddleware` sigue siendo la política deseada (SEC-01) | Nulo (es una decisión, no código) | Ninguna | N/A — es una decisión, no una corrección | Respuesta explícita documentada; si cambia, revertir siguiendo la instrucción ya escrita en el propio `middleware.py` | ✅ Confirmado: se mantiene activo |

### P1 — Alta

**Estado: resuelto el 2026-10-23** (ver nota de actualización al inicio del documento).

| Acción | Esfuerzo | Dependencias | Riesgo | Criterio de aceptación | Estado |
|---|---|---|---|---|---|
| Unificar el camino de cambio de `estado` en Nota/Pedido (API-01) | Medio | Confirmar con la usuaria si se usa la edición manual de estado | Bajo-medio (puede romper un flujo manual existente) | Las fechas de auditoría quedan correctas sin importar el camino de entrada | ✅ `Pedido.save()` + 6 tests |
| Tests del módulo admin de usuarios/roles (TEST-01) | Bajo-medio | Ninguna | Nulo | Clase de test nueva en verde, cubre las 9 rutas | ✅ `AdminPermisosTest` (9 tests) |
| Agregar `creado_por`/`anulado_por` a `Movimiento` (STK-03) | Medio (migración + ajuste de vistas) | Ninguna | Bajo (campo nullable) | Todo movimiento nuevo queda asociado a un usuario | ✅ migración 0056 + 5 tests |
| `CheckConstraint` de cantidad positiva en `MovimientoDetalle` (DB-01) | Bajo (una vez validados los datos) | Verificar datos históricos en la base real primero | Medio (la migración puede fallar si hay datos sucios) | Migración aplica limpia; `IntegrityError` ante `cantidad<=0` por ORM directo | ✅ migración 0057 — **corregida en la implementación**: la constraint real es `cantidad != 0` (no `> 0`), ver nota de actualización — `cantidad > 0` rompía el ajuste de stock a la baja (`AJUSTE` con delta negativo), un caso real ya cubierto por un test existente que casi se pasa por alto |

### P2 — Media
| Acción | Esfuerzo | Dependencias | Riesgo | Criterio de aceptación |
|---|---|---|---|---|
| Cerrar ventana de condición de carrera en verificación de stock (STK-02) | Medio-alto | Confirmar modelo de concurrencia real de uso | Medio | Test de concurrencia (TEST-03) pasa |
| Decidir el futuro del combo (`ItemComponente`) (STK-04) | Variable según decisión | Decisión de negocio | Variable | Combo funciona de punta a punta, o se retira limpio |
| Índices en `Movimiento` (PERF-01) | Bajo | Ninguna | Nulo | Migración `AddIndex` aplicada |
| Protección de doble-submit en formularios (FE-01) | Bajo-medio | Ninguna | Bajo | Doble click no crea registros duplicados |
| `collectstatic` con verificación de error en `build.ps1` (OPS-001) | Bajo | Ninguna | Nulo | Build aborta ante fallo de collectstatic |
| Contraseña no hardcodeada en `seed_demo` (OPS-006) | Bajo | Ninguna | Nulo | Sin contraseña fija en código ni README |
| Ampliar asserts de los smoke tests más críticos (TEST-02) | Medio | Ninguna | Nulo | Tests de altas de stock/reportes assertean contenido, no solo status |

### P3 — Baja
| Acción | Esfuerzo | Dependencias | Riesgo |
|---|---|---|---|
| Unificar `forms/__init__.py` (ARQ-01) | Bajo | Ninguna | Nulo |
| Mover/retirar `diagrama_app.html` (ARQ-03) | Nulo | Decisión | Nulo |
| Actualizar conteo de tests en README (ARQ-04) | Nulo | Ninguna | Nulo |
| Decidir alcance del admin de Django (ARQ-05) | Variable | Decisión | Variable |
| Extraer helper común de "agregar fila a formset" (DUP-01) | Medio | Ninguna | Bajo (requiere prueba manual en navegador) |
| Retirar `hay_stock_suficiente()` (STK-05) y `convert_movimientos.py` (OPS-003) | Nulo | Confirmar que no se usan | Nulo |
| Paginar Pendientes (FE-04) | Bajo | Ninguna | Bajo |
| Corregir doble-label en `articulo_form.html` (FE-03) | Nulo | Ninguna | Nulo |
| Filtro por default en reportes sin mes (PERF-02) | Bajo | Decisión de UX | Bajo |
| Agregar `ruff` al CI (OPS-005) | Bajo | Limpiar las 31 violaciones actuales primero | Bajo |
| Extender `SinNMasUnoTest` a más vistas (TEST-05) | Bajo | Ninguna | Nulo |
| Quitar import sin uso en `impresoras.py` (TEST-04) | Nulo | Ninguna | Nulo |

---

## 8. Mejoras de diseño y arquitectura

**Necesarias (ligadas a hallazgos ya documentados):**
- Backup automático de la base — ya cubierto en el plan P0, es la mejora de mayor beneficio/costo de todo el informe.
- Consolidar la lógica de transición de estados de Nota/Pedido en un único lugar (modelo o servicio), en vez de repartida entre `views/*_avanzar` y el guardado estándar del formulario.

**Opcionales (beneficio moderado, no urgentes):**
- Helper JS único para "agregar fila a formset" (DUP-01) — beneficio real pero acotado, dado que hoy no hay bug activo.
- Extender el admin de Django a entidades transaccionales como vía de contingencia — útil pero no imprescindible si la UI custom es confiable.

**Explícitamente NO recomendadas en este informe:**
- Reescribir la arquitectura general: la organización actual (un módulo de vistas/forms por entidad, capa de servicios delgada) es adecuada para el tamaño del sistema y no muestra señales de necesitar un cambio estructural.
- Migrar de SQLite a otro motor: no hay evidencia en este código de que el volumen de datos lo justifique; es una decisión a revisar solo si cambia el modelo de despliegue (ver pregunta pendiente de multi-PC en sección 9).
- Introducir un framework JS/SPA: el frontend actual cumple su función con buena disciplina de accesibilidad; no hay evidencia de que la complejidad de un SPA se justifique para este tamaño de aplicación.

---

## 9. Aspectos que requieren decisión funcional

1. **¿`AutoLoginMiddleware` sigue siendo la política deseada hoy?** Ya se revirtió una vez por el mismo motivo (según el propio comentario del código, fechado 2026-09-07). De la respuesta depende la severidad real de SEC-01, SEC-02 y OPS-006.

2. **¿El combo (`ItemComponente`/`Item.es_combo`) sigue siendo una funcionalidad deseada?** Si sí, falta toda la lógica de negocio (descuento de componentes al egresar un combo); si no, conviene retirarlo antes de que alguien lo use desde el admin esperando que funcione.

3. **¿Existen datos históricos con `cantidad <= 0` en `MovimientoDetalle` en la base real?** Condiciona si se puede agregar directamente el `CheckConstraint` de DB-01 o si primero hace falta limpiar datos. No verificable sin acceder a la base real (fuera del alcance de esta auditoría).

4. **¿El sistema se usa alguna vez desde más de un puesto/usuario concurrente contra la misma base de datos?** Condiciona la severidad real de STK-02 (condición de carrera) y si vale la pena construir TEST-03. Si cada instalación es siempre de un solo usuario a la vez, el riesgo baja mucho.

5. **¿Se espera inventario compartido entre varias PCs/puestos de la organización, o cada instalación de escritorio es intencionalmente independiente?** Hoy cada instalación tiene su propia base SQLite en `%APPDATA%` de esa máquina/usuario, sin ningún mecanismo de sincronización. Si la intención es "una sola PC oficial administra todo", el diseño actual es coherente. Si varias personas en distintos puestos necesitan ver/editar el mismo inventario, hoy eso no es posible y cada una vería datos desincronizados sin aviso.

6. **¿Se quiere que el admin de Django cubra las entidades transaccionales (Pedido, Nota, Reparación, etc.) como vía de contingencia, o es deliberado que solo cubra catálogos base?**

7. **¿Se necesita poder editar manualmente el campo `estado` de Nota/Pedido desde el formulario normal (para corregir errores de carga), o debería restringirse el cambio de estado solo a los botones de "avanzar"?** Condiciona la solución de API-01.

---

## 10. Limitaciones y conclusión

**Qué no se pudo verificar:**
- Cualquier dato de la base real (volumen, datos históricos sucios, combos ya cargados) — por diseño de esta auditoría de solo lectura.
- Comportamiento visual real en navegador de los hallazgos de frontend (FE-01, FE-03, FE-04) — se confirmaron por lectura de código/HTML generado, no por interacción real ni por axe-core.
- Impacto medido (no inferido) de los hallazgos de rendimiento (PERF-01, PERF-02) — requieren volumen de datos representativo, que no existe en la base de test vacía.
- Condiciones de carrera reales (STK-02) — razonadas desde el código y la semántica de SQLite/Django, no reproducidas con tráfico concurrente real.
- Vulnerabilidades conocidas en las dependencias pineadas (`Django==5.2.10`, `waitress==3.0.2`, etc.) — no se instaló ninguna herramienta de escaneo, por restricción explícita de la auditoría.

**Evidencia que haría falta para cerrar esas preguntas:**
- Respuesta a las 7 preguntas de la sección 9.
- Una copia de trabajo (no la real) de la base de datos con volumen representativo, para medir PERF-01/PERF-02 y confirmar DB-01 con seguridad.
- Una corrida de `pip-audit -r requirements.txt` en un entorno aislado (de solo lectura, sin actualizar nada).
- Una pasada de testing manual en navegador real para FE-01/FE-03/FE-04, idealmente con axe-core como ya hace el propio equipo.

**Próximo paso recomendado:** resolver primero las 3 acciones P0 (todas de bajo esfuerzo y sin ambigüedad técnica, salvo SEC-01 que es puramente una decisión), después usar las respuestas a la sección 9 para calibrar la prioridad real de P1/P2, que hoy están priorizadas de forma conservadora por falta de esa información.

**Conclusión:** StockFlow es un sistema chico pero bien cuidado para su escala — el código muestra señales consistentes de que los bugs reales se cazan y se corrigen con disciplina (N+1, accesibilidad, backfills de migración). El riesgo más alto no está en la lógica de negocio sino en la ausencia total de backup de la única copia de los datos reales, combinado con una migración automática silenciosa en cada arranque — eso es lo primero que hay que resolver, independientemente de cualquier otra prioridad de este informe.
