import os
import sys
import logging

# ─── Modo --noconsole: evitar crash por None en stdout/stderr ───
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
if sys.stdin is None:
    sys.stdin = open(os.devnull, "r")

# Logging a archivo para diagnóstico cuando corre sin consola
_APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
_LOG_DIR = os.path.join(_APPDATA, "StockToner")
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
import socket
import urllib.request

import webview
from waitress import serve


def get_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(url: str, timeout_seconds: float = 30.0) -> None:
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

    # Genera archivos estáticos si corre desde fuente (no .exe)
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
    logging.info("Iniciando InventarioHEEP")
    port = get_free_port()
    url = f"http://127.0.0.1:{port}/"

    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()

    wait_for_server(url)
    logging.info("Servidor listo en %s", url)

    webview.create_window(
        "InventarioHEEP",
        url,
        width=1280,
        height=820,
        min_size=(800, 600),
    )
    webview.start()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logging.exception("Error fatal al iniciar")
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            f"No se pudo iniciar InventarioHEEP.\n\nDetalle:\n{exc}\n\n"
            f"Revisá el log en:\n{os.path.join(_LOG_DIR, 'app.log')}",
            "InventarioHEEP — Error",
            0x10,
        )
