#desktop.py
import os
import threading
import time

import webview
from django.core.management import execute_from_command_line

def run_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    # Importante: --noreload para PyInstaller
    execute_from_command_line([
        "manage.py",
        "runserver",
        "127.0.0.1:8000",
        "--noreload",
    ])

def main():
    t = threading.Thread(target=run_django, daemon=True)
    t.start()

    # Espera mínima para que el server levante
    time.sleep(1.2)

    webview.create_window(
        "StockToner",
        "http://127.0.0.1:8000/",
        width=1200,
        height=800
    )
    webview.start()

if __name__ == "__main__":
    main()
