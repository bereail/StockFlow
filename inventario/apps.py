from django.apps import AppConfig
from django.db.backends.signals import connection_created


class InventarioConfig(AppConfig):
    name = 'inventario'

    def ready(self):
        connection_created.connect(_registrar_funciones_sqlite)


def _registrar_funciones_sqlite(sender, connection, **kwargs):
    if connection.vendor != "sqlite":
        return
    from .services.busqueda import sin_acentos
    connection.connection.create_function("sin_acentos", 1, sin_acentos, deterministic=True)
