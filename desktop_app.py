import os
import sys
import json
import logging
import socket
import threading
import time
import urllib.request
import ctypes

# ─── Modo --noconsole: evitar crash por None en stdout/stderr ───
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
if sys.stdin is None:
    sys.stdin = open(os.devnull, "r")

# ─── Logging y directorio persistente ─────────────────────────────────────────
_APPDATA  = os.environ.get("APPDATA", os.path.expanduser("~"))
_APP_DIR  = os.path.join(_APPDATA, "StockToner")
os.makedirs(_APP_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(_APP_DIR, "app.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)

# ─── Forza Edge Chromium ───────────────────────────────────────────────────────
os.environ["PYWEBVIEW_GUI"] = "edgechromium"

import webview
from waitress import serve

# ─── Agrupa correctamente en la barra de tareas de Windows ────────────────────
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        "HEEP.InventarioHEEP.1"
    )
except Exception:
    pass

# ─── Instancia única ──────────────────────────────────────────────────────────
_INSTANCE_LOCK: socket.socket | None = None

def _ensure_single_instance() -> None:
    global _INSTANCE_LOCK
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 27193))
        sock.listen(1)
        _INSTANCE_LOCK = sock
    except OSError:
        sock.close()
        ctypes.windll.user32.MessageBoxW(
            0,
            "InventarioHEEP ya está abierto.\n\nBuscala en la barra de tareas.",
            "InventarioHEEP",
            0x40,
        )
        sys.exit(0)

# ─── Persistencia de tamaño de ventana ────────────────────────────────────────
_STATE_FILE = os.path.join(_APP_DIR, "window_state.json")

def _load_window_state() -> dict:
    try:
        with open(_STATE_FILE, encoding="utf-8") as f:
            s = json.load(f)
            if s.get("width", 0) > 400 and s.get("height", 0) > 300:
                return s
    except Exception:
        pass
    return {"width": 1280, "height": 820}

def _state_saver(win: "webview.Window") -> None:
    """Guarda el tamaño real de la ventana cada 20 segundos."""
    time.sleep(8)
    while True:
        try:
            w = win.evaluate_js("window.outerWidth")
            h = win.evaluate_js("window.outerHeight")
            if w and h and int(w) > 400 and int(h) > 300:
                with open(_STATE_FILE, "w", encoding="utf-8") as f:
                    json.dump({"width": int(w), "height": int(h)}, f)
        except Exception:
            break
        time.sleep(20)

# ─── JS inyectado en cada carga para comportamiento nativo ────────────────────
_DESKTOP_JS = r"""
(function () {
    if (window._heepNative) return;
    window._heepNative = true;

    /* Sin menú contextual del browser */
    document.addEventListener('contextmenu', function (e) {
        e.preventDefault();
    }, true);

    /* Sin zoom Ctrl+rueda ni Ctrl+pinch */
    document.addEventListener('wheel', function (e) {
        if (e.ctrlKey) e.preventDefault();
    }, { passive: false });

    /* Bloquear atajos que rompen la experiencia de app */
    document.addEventListener('keydown', function (e) {
        var ctrl = e.ctrlKey || e.metaKey;
        var blocked =
            e.key === 'F5'  ||
            e.key === 'F12' ||
            (ctrl && (e.key === 'r' || e.key === 'R')) ||
            (ctrl && (e.key === 'u' || e.key === 'U')) ||
            (ctrl && e.shiftKey && (e.key === 'i' || e.key === 'I')) ||
            (ctrl && (e.key === '+' || e.key === '-' || e.key === '0'));
        if (blocked) e.preventDefault();
    }, true);

    /* Sin arrastre de imágenes ni texto de UI */
    document.addEventListener('dragstart', function (e) {
        if (!e.target.matches('input[type="file"]')) e.preventDefault();
    }, true);
})();
"""

# ─── Pantalla de splash ────────────────────────────────────────────────────────
SPLASH_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    height: 100%; background: #060f1e;
    display: flex; align-items: center; justify-content: center;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    overflow: hidden; user-select: none;
  }
  .card {
    display: flex; flex-direction: column; align-items: center; gap: 10px;
    animation: entrada .5s cubic-bezier(.22,1,.36,1) both;
  }
  @keyframes entrada {
    from { opacity:0; transform:translateY(20px) scale(.97); }
    to   { opacity:1; transform:none; }
  }
  .logo-wrap {
    width:80px; height:80px;
    background: linear-gradient(135deg,#1a3a6e 0%,#2d5fb3 100%);
    border-radius:22px; display:flex; align-items:center; justify-content:center;
    margin-bottom:6px;
    box-shadow: 0 0 0 1px rgba(79,140,255,.18),
                0 16px 48px rgba(0,0,0,.55),
                inset 0 1px 0 rgba(255,255,255,.06);
  }
  .logo-wrap svg { width:42px; height:42px; }
  h1 { font-size:26px; font-weight:700; color:#f0f5ff; letter-spacing:-.4px; }
  .sub { font-size:13px; color:#4f6e96; margin-bottom:28px; letter-spacing:.2px; }
  .track { width:180px; height:3px; background:rgba(79,140,255,.12); border-radius:99px; overflow:hidden; }
  .fill  { height:100%; width:40%;
           background:linear-gradient(90deg,#1a3a6e,#4f8cff); border-radius:99px;
           animation:slide 1.4s ease-in-out infinite; }
  @keyframes slide { 0%{transform:translateX(-200%)} 100%{transform:translateX(500%)} }
</style>
</head>
<body>
<div class="card">
  <div class="logo-wrap">
    <svg viewBox="0 0 24 24" fill="none" stroke="#4f8cff"
         stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
      <rect x="6" y="2" width="12" height="8" rx="1"/>
      <path d="M4 10h16a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2z"/>
      <rect x="7" y="16" width="10" height="6" rx="1"/>
      <circle cx="18" cy="14" r="1" fill="#4f8cff" stroke="none"/>
    </svg>
  </div>
  <h1>InventarioHEEP</h1>
  <p class="sub">Iniciando sistema…</p>
  <div class="track"><div class="fill"></div></div>
</div>
</body>
</html>"""


class AppAPI:
    """API expuesta a JS via window.pywebview.api"""
    _win = None

    def save_csv(self, b64data: str, suggested_name: str) -> str | None:
        """Muestra diálogo nativo de guardar y escribe el archivo."""
        import base64
        try:
            result = self._win.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=os.path.join(os.path.expanduser("~"), "Downloads"),
                save_filename=suggested_name or "descarga.csv",
                file_types=("Archivos HTML (*.html)", "Archivos CSV (*.csv)", "Todos los archivos (*.*)")
            )
            if result:
                path = result if isinstance(result, str) else result[0]
                data = base64.b64decode(b64data)
                with open(path, "wb") as f:
                    f.write(data)
                logging.info("CSV guardado: %s", path)
                return path
        except Exception:
            logging.exception("Error al guardar CSV")
        return None


def get_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(url: str, timeout_seconds: float = 45.0) -> None:
    start      = time.time()
    last_error = None
    while True:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status in (200, 301, 302, 403):
                    return
        except Exception as e:
            last_error = e
        if time.time() - start > timeout_seconds:
            raise RuntimeError(
                f"El servidor no respondió en {timeout_seconds}s.\n"
                f"Último error: {last_error}"
            )
        time.sleep(0.2)


def setup_django() -> None:
    BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    os.chdir(BASE_DIR)
    sys.path.insert(0, BASE_DIR)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django
    django.setup()

    from django.core.management import call_command
    call_command("migrate", "--run-syncdb", verbosity=0)

    if not getattr(sys, "frozen", False):
        call_command("collectstatic", "--noinput", verbosity=0)


def run_server(port: int) -> None:
    try:
        setup_django()
        from django.core.wsgi import get_wsgi_application
        serve(get_wsgi_application(), host="127.0.0.1", port=port, threads=8)
    except Exception:
        logging.exception("Error fatal en el servidor")
        raise


def main() -> None:
    _ensure_single_instance()
    logging.info("Iniciando InventarioHEEP")

    state = _load_window_state()
    port  = get_free_port()
    url   = f"http://127.0.0.1:{port}/"

    api = AppAPI()

    window = webview.create_window(
        "InventarioHEEP",
        html=SPLASH_HTML,
        width=state["width"],
        height=state["height"],
        min_size=(800, 600),
        js_api=api,
    )
    api._win = window

    # ── Inyectar JS nativo + actualizar título en cada carga de página ──
    def _on_loaded():
        try:
            window.evaluate_js(_DESKTOP_JS)
            title = window.evaluate_js("document.title")
            if title and title.strip():
                window.title = title.strip()
        except Exception:
            pass

    window.events.loaded += _on_loaded

    # ── Guardar tamaño de ventana en segundo plano ──
    def _start_state_saver():
        threading.Thread(target=_state_saver, args=(window,), daemon=True).start()

    window.events.shown += _start_state_saver

    # ── Servidor Django en segundo plano ──
    threading.Thread(target=run_server, args=(port,), daemon=True).start()

    def _cargar_cuando_listo():
        try:
            wait_for_server(url)
            logging.info("Servidor listo en %s", url)
            window.load_url(url)
        except Exception:
            logging.exception("Error esperando el servidor")

    webview.start(func=_cargar_cuando_listo)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logging.exception("Error fatal al iniciar")
        ctypes.windll.user32.MessageBoxW(
            0,
            f"No se pudo iniciar InventarioHEEP.\n\nDetalle:\n{exc}\n\n"
            f"Revisá el log en:\n{os.path.join(_APP_DIR, 'app.log')}",
            "InventarioHEEP — Error",
            0x10,
        )
