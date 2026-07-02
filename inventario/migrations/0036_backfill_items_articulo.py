from django.db import migrations


def crear_items_articulo(apps, schema_editor):
    Articulo = apps.get_model("inventario", "Articulo")
    Item = apps.get_model("inventario", "Item")
    for articulo in Articulo.objects.all():
        Item.objects.get_or_create(tipo="ARTICULO", articulo=articulo)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0035_impresora_articulo"),
    ]

    operations = [
        migrations.RunPython(crear_items_articulo, noop),
    ]
