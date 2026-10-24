from django.db import migrations

TABLA_RESPALDO = '_migracion_consulta_especialidad'


def completar_especialidades(apps, schema_editor):
    """Completa el texto de las consultas que quedaron sin especialidad.

    Guardamos en una tabla de respaldo el valor exacto que se completó para
    poder revertir sin tocar textos históricos cargados por otros medios.
    """
    Consulta = apps.get_model('historias', 'Consulta')

    schema_editor.execute(
        f'CREATE TABLE IF NOT EXISTS "{TABLA_RESPALDO}" ('
        '"consulta_id" integer PRIMARY KEY, '
        '"valor_completado" text NOT NULL)'
    )

    consultas = Consulta.objects.filter(especialidad='').prefetch_related(
        'profesional__especialidades',
    )
    for consulta in consultas.iterator(chunk_size=500):
        nombres = [e.nombre for e in consulta.profesional.especialidades.all()]
        if not nombres:
            continue

        valor = ', '.join(nombres)[:50]
        consulta.especialidad = valor
        consulta.save(update_fields=['especialidad'])

        schema_editor.execute(
            f'DELETE FROM "{TABLA_RESPALDO}" WHERE "consulta_id" = %s',
            [consulta.pk],
        )
        schema_editor.execute(
            f'INSERT INTO "{TABLA_RESPALDO}" '
            '("consulta_id", "valor_completado") VALUES (%s, %s)',
            [consulta.pk, valor],
        )


def revertir_especialidades(apps, schema_editor):
    """Restaura las consultas que esta migración completó."""
    Consulta = apps.get_model('historias', 'Consulta')

    tablas = schema_editor.connection.introspection.table_names()
    if TABLA_RESPALDO not in tablas:
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f'SELECT "consulta_id", "valor_completado" FROM "{TABLA_RESPALDO}"'
        )
        respaldos = cursor.fetchall()

    for consulta_id, valor in respaldos:
        # Solo limpiamos si la consulta conserva exactamente el texto que
        # agregó esta migración. Si fue editada después, se respeta el dato.
        Consulta.objects.filter(pk=consulta_id, especialidad=valor).update(
            especialidad=''
        )

    schema_editor.execute(f'DROP TABLE IF EXISTS "{TABLA_RESPALDO}"')


class Migration(migrations.Migration):

    dependencies = [
        ('historias', '0003_alter_consulta_archivo_adjunto'),
        (
            'profesionales',
            '0002_especialidad_remove_profesional_especialidad_and_more',
        ),
    ]

    operations = [
        migrations.RunPython(
            completar_especialidades,
            revertir_especialidades,
        ),
    ]
