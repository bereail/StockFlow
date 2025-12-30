import os
from django.core.management import execute_from_command_line

def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    execute_from_command_line([
        "manage.py",
        "runserver",
        "127.0.0.1:8000",
        "--noreload",
    ])

if __name__ == "__main__":
    main()
