#run_app.py
import os
import sys

def fix_std_streams():
    # En modo --noconsole, stdout/stderr pueden ser None
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    if sys.stdin is None:
        sys.stdin = open(os.devnull, "r")

def main():
    fix_std_streams()

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


    from django.core.management import execute_from_command_line

    # Levanta el server sin autoreload (evita problemas en .exe)
    execute_from_command_line([
        "manage.py",
        "runserver",
        "127.0.0.1:8000",
        "--noreload",
    ])

if __name__ == "__main__":
    main()
