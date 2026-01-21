import os
import sys
import threading
import socket
import time
import urllib.request

import webview
from waitress import serve


def get_free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def wait_for_server(url: str, timeout_seconds: float = 8.0) -> None:
    start = time.time()
    while True:
        try:
            with urllib.request.urlopen(url) as r:
                if r.status == 200:
                    return
        except Exception:
            pass

        if time.time() - start > timeout_seconds:
            raise RuntimeError("El servidor Django no respondió a tiempo.")
        time.sleep(0.15)


def run_server(port: int) -> None:
    # Asegura que el root del proyecto esté en el path (misma carpeta que manage.py)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, BASE_DIR)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django
    django.setup()

    from django.core.wsgi import get_wsgi_application
    app = get_wsgi_application()

    serve(app, host="127.0.0.1", port=port)


def main():
    port = get_free_port()
    url = f"http://127.0.0.1:{port}/"

    t = threading.Thread(target=run_server, args=(port,), daemon=True)
    t.start()

    # Espera real a que el server esté listo
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
