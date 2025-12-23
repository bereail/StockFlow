import os
import sys
import threading
import time
import subprocess
import socket
import shutil
import webview


# Ruta base (PyInstaller o normal)
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE_DIR)

APP_NAME = "StockToner"


def get_data_dir():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        # fallback (raro), pero evita crash
        return os.path.join(BASE_DIR, APP_NAME)
    return os.path.join(appdata, APP_NAME)


def ensure_appdata_db():
    """
    Si es la primera vez que corre, copia la DB base embebida (con catálogo)
    hacia AppData, que es donde queda persistente.
    """
    data_dir = get_data_dir()
    os.makedirs(data_dir, exist_ok=True)

    dst = os.path.join(data_dir, "db.sqlite3")
    src = os.path.join(BASE_DIR, "db.sqlite3")  # DB base incluida en el build

    if not os.path.exists(dst) and os.path.exists(src):
        shutil.copy2(src, dst)


def seed_if_needed():
    """
    Carga fixtures si la DB está vacía (no rompe si falla).
    """
    try:
        subprocess.run([sys.executable, "manage.py", "seed"], check=False)
    except Exception:
        pass


def find_free_port(host="127.0.0.1"):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((host, 0))
    port = s.getsockname()[1]
    s.close()
    return port


def run_django(port: int):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(["manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"])


def wait_for_server(url, timeout=12.0):
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status in (200, 301, 302, 403, 404):
                    return True
        except Exception:
            time.sleep(0.2)
    return False


if __name__ == "__main__":
    # 1) persistencia: DB en AppData
    ensure_appdata_db()

    # 2) seed si DB vacía
    seed_if_needed()

    # 3) puerto libre + server
    port = find_free_port()
    url = f"http://127.0.0.1:{port}/"

    t = threading.Thread(target=run_django, args=(port,), daemon=True)
    t.start()

    wait_for_server(url)

    # 4) UI
    webview.create_window("Stock Toner", url)
    webview.start()
