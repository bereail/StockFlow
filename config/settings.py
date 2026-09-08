from pathlib import Path
import os
import sys

# =========================
# BASE DIR
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent

# Si corre como .exe (PyInstaller)
FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    BASE_DIR = Path(sys._MEIPASS)

# =========================
# SECURITY
# =========================
APP_NAME = "StockToner"
APPDATA_DIR = os.path.join(os.environ.get("APPDATA", str(BASE_DIR)), APP_NAME)
os.makedirs(APPDATA_DIR, exist_ok=True)

# La SECRET_KEY se genera una única vez por instalación y se persiste junto a
# la base de datos en APPDATA. Evita tener una clave fija en el repo/binario.
_secret_key_path = os.path.join(APPDATA_DIR, "secret.key")
if os.path.exists(_secret_key_path):
    with open(_secret_key_path, "r", encoding="utf-8") as f:
        SECRET_KEY = f.read().strip()
else:
    from django.core.management.utils import get_random_secret_key
    SECRET_KEY = get_random_secret_key()
    with open(_secret_key_path, "w", encoding="utf-8") as f:
        f.write(SECRET_KEY)

# DEBUG solo en desarrollo (nunca en el .exe empaquetado). Se puede forzar
# con la variable de entorno STOCKTONER_DEBUG=1 si hace falta depurar el build.
DEBUG = (not FROZEN) or os.environ.get("STOCKTONER_DEBUG") == "1"
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# =========================
# APPLICATIONS
# =========================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "inventario",
]

# =========================
# MIDDLEWARE
# =========================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "inventario.middleware.AutoLoginMiddleware",  # TEMPORAL de nuevo, a pedido — ver middleware.py
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# =========================
# TEMPLATES
# =========================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "inventario" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "inventario.context_processors.global_settings",
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# =========================
# DATABASE (APPDATA – PERSISTENTE)
# =========================
APP_NAME = "StockToner"
APPDATA_DIR = os.path.join(os.environ.get("APPDATA", str(BASE_DIR)), APP_NAME)
os.makedirs(APPDATA_DIR, exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(APPDATA_DIR, "db.sqlite3"),
    }
}


# =========================
# I18N / TIMEZONE
# =========================
LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Cordoba"
USE_I18N = True
USE_TZ = True

# =========================
# STATIC FILES
# =========================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [] 

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Cuando corre como .exe, usa StaticFilesStorage simple (sin manifest)
if getattr(sys, "frozen", False):
    STATICFILES_STORAGE = "whitenoise.storage.StaticFilesStorage"
else:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# =========================
# AUTH
# =========================
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# =========================
# SESSIONS / CSRF
# =========================
# La app corre por HTTP en loopback (127.0.0.1), nunca en HTTPS, así que las
# cookies "Secure" no aplican acá. Se declaran explícitas para que la
# intención quede clara en vez de depender del default de Django.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_SAMESITE = "Lax"