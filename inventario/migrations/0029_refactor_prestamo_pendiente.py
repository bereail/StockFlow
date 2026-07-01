from django.db import migrations, models


def migrar_estado(apps, schema_editor):
    Pendiente = apps.get_model("inventario", "Pendiente")
    Pendiente.objects.filter(completado=True).update(estado="COMPLETADO")


def revertir_estado(apps, schema_editor):
    Pendiente = apps.get_model("inventario", "Pendiente")
    Pendiente.objects.filter(estado="COMPLETADO").update(completado=True)


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0028_item_es_combo"),
    ]

    operations = [
        migrations.AddField(
            model_name="pendiente",
            name="estado",
            field=models.CharField(
                choices=[
                    ("PENDIENTE", "Pendiente"),
                    ("EN_PROGRESO", "En progreso"),
                    ("COMPLETADO", "Completado"),
                    ("CANCELADO", "Cancelado"),
                ],
                default="PENDIENTE",
                max_length=20,
                db_index=True,
            ),
        ),
        migrations.RunPython(migrar_estado, revertir_estado),
        migrations.AddField(
            model_name="pendiente",
            name="fecha_limite",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.RemoveField(model_name="pendiente", name="completado"),
        migrations.AlterModelOptions(
            name="pendiente",
            options={"ordering": ["estado", "-creado"]},
        ),
        migrations.RemoveField(model_name="prestamo", name="proyector"),
        migrations.RemoveField(model_name="prestamo", name="camara_web"),
        migrations.RemoveField(model_name="prestamo", name="prolongacion"),
        migrations.RemoveField(model_name="prestamo", name="notebook"),
        migrations.RemoveField(model_name="item", name="categoria_prestamo"),
    ]
