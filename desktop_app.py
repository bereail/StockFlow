import os
os.environ["PYWEBVIEW_GUI"] = "edgechromium"

import sys
import threading
import time
import socket
import urllib.request
import urllib.error

import webview
from waitress import serve


def get_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(url: str, timeout_seconds: float = 15.0) -> None:
    start = time.time()
    last_error = None

    while True:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2) as r:
                # Django puede responder 200 o redirigir (301/302) si no estás logueada
                if r.status in (200, 301, 302, 403):
                    return
        except Exception as e:
            last_error = e

        if time.time() - start > timeout_seconds:
            raise RuntimeError(f"El servidor Django no respondió a tiempo. Último error: {last_error}")

        time.sleep(0.15)


def run_server(port: int) -> None:
    # Soporta PyInstaller (cuando corre desde el EXE)
    BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    os.chdir(BASE_DIR)
    sys.path.insert(0, BASE_DIR)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django
    django.setup()

    from django.core.wsgi import get_wsgi_application
    app = get_wsgi_application()

    # Waitress bloquea, por eso corre en thread
    serve(app, host="127.0.0.1", port=port, threads=8)


def main():
    port = get_free_port()
    url = f"http://127.0.0.1:{port}/"

    t = threading.Thread(target=run_server, args=(port,), daemon=True)
    t.start()

    wait_for_server(url)

    webview.create_window(
        "StockToner",
        url,
        width=1200,
        height=800,
    )
    webview.start()


if __name__ == "__main__":
    main()
