import os
import sys
import logging
import socket

# ─── Modo --noconsole: evitar crash por None en stdout/stderr ───
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
if sys.stdin is None:
    sys.stdin = open(os.devnull, "r")

# Logging a archivo — diagnóstico cuando corre sin consola
_APPDATA  = os.environ.get("APPDATA", os.path.expanduser("~"))
_LOG_DIR  = os.path.join(_APPDATA, "StockToner")
os.makedirs(_LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(_LOG_DIR, "app.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)

# Forza Edge Chromium para pywebview en Windows
os.environ["PYWEBVIEW_GUI"] = "edgechromium"

import threading
import time
import urllib.request
import ctypes

import webview
from waitress import serve

# ─── AppUserModelID: Windows agrupa la app correctamente en la barra de tareas
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("HEEP.InventarioHEEP.1")
except Exception:
    pass

# ─── Lock de instancia única ───────────────────────────────────────────────────
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

# ─── Pantalla de splash ────────────────────────────────────────────────────────
SPLASH_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    height: 100%;
    background: #060f1e;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    overflow: hidden;
    user-select: none;
  }
  .card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    animation: entrada 0.5s cubic-bezier(.22,1,.36,1) both;
  }
  @keyframes entrada {
    from { opacity: 0; transform: translateY(20px) scale(.97); }
    to   { opacity: 1; transform: none; }
  }
  .logo-wrap {
    width: 80px;
    height: 80px;
    background: linear-gradient(135deg, #1a3a6e 0%, #2d5fb3 100%);
    border-radius: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 6px;
    box-shadow: 0 0 0 1px rgba(79,140,255,.18),
                0 16px 48px rgba(0,0,0,.55),
                inset 0 1px 0 rgba(255,255,255,.06);
  }
  .logo-wrap svg { width: 42px; height: 42px; }
  h1 {
    font-size: 26px;
    font-weight: 700;
    color: #f0f5ff;
    letter-spacing: -0.4px;
  }
  .sub {
    font-size: 13px;
    color: #4f6e96;
    margin-bottom: 28px;
    letter-spacing: .2px;
  }
  .track {
    width: 180px;
    height: 3px;
    background: rgba(79,140,255,.12);
    border-radius: 99px;
    overflow: hidden;
  }
  .fill {
    height: 100%;
    width: 40%;
    background: linear-gradient(90deg, #1a3a6e, #4f8cff);
    border-radius: 99px;
    animation: slide 1.4s ease-in-out infinite;
  }
  @keyframes slide {
    0%   { transform: translateX(-200%); }
    100% { transform: translateX(500%); }
  }
</style>
</head>
<body>
<div class="card">
  <div class="logo-wrap">
    <!-- ícono de impresora/tóner en SVG puro -->
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


def get_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(url: str, timeout_seconds: float = 45.0) -> None:
    start = time.time()
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

    try:
        call_command("init_usuario", verbosity=0)
    except Exception:
        pass


def run_server(port: int) -> None:
    try:
        setup_django()
        from django.core.wsgi import get_wsgi_application
        app = get_wsgi_application()
        serve(app, host="127.0.0.1", port=port, threads=8)
    except Exception:
        logging.exception("Error fatal en el servidor")
        raise


def main() -> None:
    _ensure_single_instance()
    logging.info("Iniciando InventarioHEEP")

    port = get_free_port()
    url  = f"http://127.0.0.1:{port}/"

    window = webview.create_window(
        "InventarioHEEP",
        html=SPLASH_HTML,
        width=1280,
        height=820,
        min_size=(800, 600),
    )

    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()

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
            f"Revisá el log en:\n{os.path.join(_LOG_DIR, 'app.log')}",
            "InventarioHEEP — Error",
            0x10,
        )
