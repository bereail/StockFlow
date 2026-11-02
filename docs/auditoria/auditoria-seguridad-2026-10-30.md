# Auditoría de seguridad dedicada — 2026-10-30

Auditoría de solo lectura, enfocada exclusivamente en seguridad (más profunda que la pasada de seguridad incluida dentro de la auditoría integral del 23/10). No se modificó código, no se ejecutaron migraciones, no se tocó la base real (`%APPDATA%\StockToner\db.sqlite3`), no se instalaron dependencias, no se hicieron commits.

## 1. Resumen ejecutivo

**3 hallazgos nuevos** (0 críticos · 0 altos · 1 medio · 2 bajos) — ninguno de severidad crítica/alta. El sistema sigue sin SQL crudo, sin `csrf_exempt`, sin secretos commiteados y con CSRF/XSS correctamente manejados en los puntos donde se generó contenido dinámico (reportes HTML). Se reconfirmó que **SEC-01 (`AutoLoginMiddleware`)** sigue activo tal como se documentó y decidió el 23/10 — no se vuelve a cuestionar esa decisión de producto, solo se documenta su alcance real para contexto de los hallazgos nuevos.

| ID | Hallazgo | Gravedad |
|---|---|---|
| SEC-N1 | Open redirect en `custom_login` vía el parámetro `next` | Media |
| SEC-N2 | Sin límite de intentos de login (fuerza bruta) | Baja |
| SEC-N3 | El context processor expone el objeto `settings` completo a todos los templates | Baja |

**Puntos de la lista de alcance revisados y SIN hallazgos nuevos:**
- **CSRF:** cero usos de `csrf_exempt` en todo el proyecto; las únicas llamadas AJAX (`fetch`) son GET de solo lectura, no requieren token.
- **Inyección SQL / XSS:** sin `.raw()`/`.extra()`/`cursor.execute()` con datos de usuario; sin `|safe`/`mark_safe` en ningún template; los 5 reportes HTML (`reportes.py`) escapan consistentemente cada valor dinámico con `django.utils.html.escape` antes de interpolarlo.
- **Configuración (`settings.py`):** `DEBUG` correctamente atado a `FROZEN`/variable de entorno explícita; `ALLOWED_HOSTS` acotado a loopback; `SECRET_KEY` generada una sola vez por instalación y persistida fuera del repo (nunca hardcodeada); cookies de sesión/CSRF con flags explícitos y justificados por el modelo de despliegue (HTTP loopback, nunca HTTPS).
- **Manejo de archivos:** no hay ningún `request.FILES`/`FileField` en todo el proyecto — no hay superficie de subida de archivos. Backups y rutas de `backups.py` no dependen de input de usuario (sin path traversal posible).
- **Dependencias:** todas ancladas con `==` en `requirements.txt` (Django 5.2.10, waitress 3.0.2, whitenoise 6.11.0, pywebview 6.1, pyinstaller 6.17.0, openpyxl 3.1.5). No se pudo correr un scan de CVE real sin acceso a internet; a nivel de versión no se ve nada obviamente desactualizado.
- **Empaquetado desktop:** `desktop_app.py`/`StockToner.spec` no embeben ningún secreto, credencial ni ruta sensible — el `.spec` solo empaqueta `staticfiles/` y templates; la `SECRET_KEY` se genera en runtime y vive en `APPDATA`, nunca en el `.exe`.
- **Logging:** sin contraseñas/tokens/secretos logueados en ningún `logging.*()` del proyecto.
- **Panel de admin (`/admin/` + ARQ-05):** acceso gateado por `is_staff`/`is_superuser` como corresponde; los modelos transaccionales agregados en la sesión del 23/10 (Pedido, Nota, Movimiento, etc.) ya llevan en el propio `admin.py` un comentario explícito de que es "vía de contingencia manual" que bypassea las reglas de negocio de la UI — decisión ya tomada y documentada, no es un hallazgo nuevo.
- **IDOR:** no aplica como vulnerabilidad — el modelo de datos es de visibilidad institucional compartida por diseño (cualquier usuario autenticado ve todos los servicios/inventario del hospital), no hay un límite de pertenencia que un `pk` ajeno pueda violar.
- **Autorización:** los 16 módulos de vistas mantienen `@login_required`/`@require_POST`/`user_passes_test` de forma consistente, sin excepciones encontradas (confirmado por grep exhaustivo, no solo muestreo).

**Hallazgo reconfirmado, no nuevo:** `AutoLoginMiddleware` (`inventario/middleware.py:1-22`, activado en `config/settings.py:62`) sigue logueando automáticamente como el primer superusuario a cualquiera que abra la app sin sesión. Esto hace que SEC-N2 (sin límite de intentos de login) tenga impacto práctico bajo hoy — la puerta de autenticación real casi no se usa mientras este middleware esté activo — pero sí importaría si en el futuro se saca el middleware sin agregar protección de fuerza bruta al mismo tiempo.

---

## 2. Hallazgos detallados

### SEC-N1 — Open redirect en el login vía el parámetro `next`
- **Categoría:** Autenticación / redirecciones no validadas
- **Gravedad:** media
- **Archivo:** `inventario/views/core.py:43-44`
- **Explicación:** `custom_login` construye `next_url` a partir de `request.POST.get("next")` / `request.GET.get("next")` y lo pasa directo a `redirect(next_url)`, sin pasar por `django.utils.http.url_has_allowed_host_and_scheme` (el chequeo que sí usa internamente `django.contrib.auth.views.LoginView`, la vista estándar de Django que esta vista reemplaza). `redirect()` no valida que el destino sea un host local.
- **Escenario concreto:** un link `/accounts/login/?next=https://sitio-falso.com/` enviado a un usuario real de la app — al loguearse correctamente, termina redirigido a un sitio externo, útil para un ataque de phishing post-login (ej. una página que imita el login de StockFlow para capturar credenciales reutilizadas en otro sistema del hospital).
- **Impacto real hoy:** bajo, porque `AutoLoginMiddleware` autentica antes de llegar a esta vista en el uso normal — el formulario de login casi no se ejercita mientras ese middleware esté activo. El riesgo se activa si el middleware se desactiva en el futuro (ya pasó una vez, según el propio comentario del middleware) sin revisar este archivo en paralelo.
- **Evidencia:** `inventario/views/core.py:25-46`.
- **Solución recomendada:** validar `next_url` con `django.utils.http.url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()})` antes de redirigir, descartando a `"dashboard"` si no pasa el chequeo — mismo patrón que usa `LoginView` de Django.
- **Prueba de verificación sugerida:** POST a `/accounts/login/` con credenciales válidas y `next=https://ejemplo-externo.test/` → hoy redirige ahí; con el fix, debe caer a `dashboard`.

### SEC-N2 — Sin límite de intentos de login (fuerza bruta)
- **Categoría:** Autenticación
- **Gravedad:** baja
- **Archivo:** `inventario/views/core.py:25-46`
- **Explicación:** `authenticate()` se llama sin ningún throttling, lockout o backoff por IP/usuario. No hay `django-axes` ni mecanismo equivalente instalado (`requirements.txt` no lo incluye).
- **Impacto real hoy:** bajo — mientras `AutoLoginMiddleware` esté activo, la puerta de login real casi no se usa (cualquiera que abra la app ya entra como superusuario sin necesitar adivinar nada). Importaría más si se revierte esa decisión, o si alguna vez la app se expone más allá de loopback/LAN de confianza.
- **Evidencia:** `inventario/views/core.py:25-46`; `requirements.txt` (sin paquete de rate-limiting).
- **Solución recomendada:** si se retoma el login real en algún momento, agregar un lockout simple (ej. `django-axes`, o un contador en caché/sesión por IP) antes de depender de contraseñas fuertes como única defensa.

### SEC-N3 — El context processor expone el objeto `settings` completo a todos los templates
- **Categoría:** Exposición de configuración / hardening
- **Gravedad:** baja
- **Archivo:** `inventario/context_processors.py:13-18`
- **Explicación:** `global_settings()` agrega `"settings": settings` al contexto de **todo** render — cualquier template de las ~64 plantillas del proyecto podría hacer `{{ settings.SECRET_KEY }}` o `{{ settings.DATABASES }}` y Django lo renderizaría como texto escapado (visible en el HTML servido, no una ejecución de código, pero sí una fuga de configuración interna si algún template llega a referenciarlo por error).
- **Impacto real hoy:** ninguno confirmado — se verificó que ningún template actual usa `{{ settings.* }}` para nada sensible (solo necesitarían, como mucho, flags públicos). Es una superficie innecesaria más que un hallazgo activo.
- **Evidencia:** `inventario/context_processors.py:16`; grep sobre `inventario/templates/` sin coincidencias de `{{ settings.`.
- **Solución recomendada:** exponer solo las claves puntuales que la UI necesita (ej. `{"debug": settings.DEBUG}` si hace falta) en vez de pasar el módulo `settings` completo.

---

## 3. Limitaciones de esta auditoría

- No se corrió un scanner de CVE contra `requirements.txt` (sin acceso a internet en esta sesión) — solo se verificó que las versiones estén ancladas y no se vean obviamente desactualizadas.
- No se evaluó seguridad de infraestructura de CI/CD (permisos del repo, secretos de GitHub Actions) — fuera del alcance pedido (código de la aplicación).
- No se re-auditaron en profundidad los hallazgos de seguridad ya cerrados de la auditoría del 23/10 (SEC-01, DB-01, etc.) más allá de reconfirmar que `AutoLoginMiddleware` sigue activo como se documentó — se asumió que el resto de las correcciones commiteadas siguen en pie salvo que el código mostrara lo contrario.
