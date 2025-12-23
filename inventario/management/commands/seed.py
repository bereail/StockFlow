from django.core.management.base import BaseCommand
from django.core.management import call_command
from inventario.models import Servicio, Toner

class Command(BaseCommand):
    help = "Carga datos iniciales (Servicios y Toners) desde fixtures si la DB está vacía."

    def handle(self, *args, **options):
        if Servicio.objects.exists() or Toner.objects.exists():
            self.stdout.write(self.style.WARNING("Seed: ya hay datos, no se carga nada."))
            return

        call_command("loaddata", "inventario/fixtures/servicios.json")
        call_command("loaddata", "inventario/fixtures/toners.json")

        self.stdout.write(self.style.SUCCESS("Seed: catálogo inicial cargado (servicios + toners)."))
