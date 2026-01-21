from django.core.management.base import BaseCommand
from inventario.models import Movimiento, MovimientoDetalle, Item

class Command(BaseCommand):
    help = "Convierte movimientos viejos (con toner/cantidad) a MovimientoDetalle"

    def handle(self, *args, **options):
        ok = 0
        for m in Movimiento.objects.all():
            # si ya tiene detalles, saltamos
            if getattr(m, "detalles").exists():
                continue

            # ajustá estos campos si tu modelo viejo era distinto:
            toner = getattr(m, "toner", None)
            cantidad = getattr(m, "cantidad", None)

            if toner and cantidad:
                item, _ = Item.objects.get_or_create(
                    tipo="TONER",
                    toner=toner,
                    defaults={"articulo": None, "activo_pc": None, "impresora": None},
                )
                MovimientoDetalle.objects.create(movimiento=m, item=item, cantidad=cantidad)
                ok += 1

        self.stdout.write(self.style.SUCCESS(f"Listo. Detalles creados: {ok}"))