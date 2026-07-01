from django.db import migrations


def crear_items_impresora(apps, schema_editor):
    Impresora = apps.get_model("inventario", "Impresora")
    Item = apps.get_model("inventario", "Item")
    for impresora in Impresora.objects.all():
        Item.objects.get_or_create(tipo="IMPRESORA", impresora=impresora)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0031_pedido_proveedor_fechas"),
    ]

    operations = [
        migrations.RunPython(crear_items_impresora, noop),
    ]
