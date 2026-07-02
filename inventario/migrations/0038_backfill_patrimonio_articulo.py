from django.db import migrations


def backfill_articulo(apps, schema_editor):
    PatrimonioUnidad = apps.get_model("inventario", "PatrimonioUnidad")
    for pat in PatrimonioUnidad.objects.filter(articulo__isnull=True, pedido_detalle__isnull=False):
        item = pat.pedido_detalle.item
        if item.articulo_id:
            pat.articulo_id = item.articulo_id
            pat.save(update_fields=["articulo"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0037_patrimoniounidad_articulo_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_articulo, noop),
    ]
