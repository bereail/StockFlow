import os
import sys
import threading
import time
import socket
import shutil
import traceback
import webview

APP_NAME = "StockToner"

# Ruta base (PyInstaller o normal)
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE_DIR)


def get_data_dir():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return os.path.join(BASE_DIR, APP_NAME)
    return os.path.join(appdata, APP_NAME)


def log(msg: str):
    """Log simple a AppData para debug en EXE."""
    try:
        data_dir = get_data_dir()
        os.makedirs(data_dir, exist_ok=True)
        log_path = os.path.join(data_dir, "app.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def ensure_appdata_db():
    data_dir = get_data_dir()
    os.makedirs(data_dir, exist_ok=True)

    dst = os.path.join(data_dir, "db.sqlite3")
    src = os.path.join(BASE_DIR, "db.sqlite3")

    if not os.path.exists(dst) and os.path.exists(src):
        shutil.copy2(src, dst)
        log("DB copiada a AppData.")


def seed_if_needed():
    """Corre seed en-proceso (NO subprocess)."""
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django
        django.setup()
        from django.core.management import call_command
        log("Ejecutando seed...")
        call_command("seed")
        log("Seed terminado.")
    except Exception:
        log("Seed falló:\n" + traceback.format_exc())


def find_free_port(host="127.0.0.1"):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((host, 0))
    port = s.getsockname()[1]
    s.close()
    return port


def run_django(port: int):
    """Arranca Django en thread y loguea cualquier crash."""
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        from django.core.management import execute_from_command_line
        log(f"Arrancando Django en puerto {port}...")
        execute_from_command_line(["manage.py", "runserver", f"0.0.0.0:{port}", "--noreload"])
    except Exception:
        log("Django crasheó:\n" + traceback.format_exc())


def wait_for_server(url, timeout=35.0):
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status in (200, 301, 302, 403, 404):
                    return True
        except Exception:
            time.sleep(0.25)
    return False


if __name__ == "__main__":
    log("DESKTOP VERSION: 2025-12-23 08:50")
    log("=== INICIO APP ===")
    log(f"BASE_DIR={BASE_DIR}")

    # 1) persistencia: DB en AppData
    ensure_appdata_db()

    # 2) seed
    seed_if_needed()

    # 3) puerto libre + server
    port = find_free_port()
    url = f"http://127.0.0.1:{port}/"
    log(f"URL={url}")

    t = threading.Thread(target=run_django, args=(port,), daemon=True)
    t.start()

    ok = wait_for_server(url, timeout=35)

    if not ok:
        log("Servidor NO respondió a tiempo.")
        webview.create_window(
            "Stock Toner - Error",
            html="""
            <html>
            <body style="font-family:sans-serif">
                <h2>No se pudo iniciar el servidor</h2>
                <p>Django no respondió a tiempo.</p>
                <p>Revisá el log: <b>%APPDATA%\\StockToner\\app.log</b></p>
            </body>
            </html>
            """
        )
        webview.start()
        sys.exit(1)

    log("Servidor OK. Abriendo UI...")
    webview.create_window("Stock Toner", url)
    webview.start()
