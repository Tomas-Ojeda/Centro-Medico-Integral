from django.db import migrations

TABLA_RESPALDO = '_migracion_turno_especialidad'


def completar_especialidades(apps, schema_editor):
    """Completa el texto de los turnos que quedaron sin especialidad.

    Guardamos en una tabla de respaldo el valor exacto que se completó para
    poder revertir sin tocar textos históricos cargados por otros medios.
    """
    Turno = apps.get_model('turnos', 'Turno')

    schema_editor.execute(
        f'CREATE TABLE IF NOT EXISTS "{TABLA_RESPALDO}" ('
        '"turno_id" integer PRIMARY KEY, '
        '"valor_completado" text NOT NULL)'
    )

    turnos = Turno.objects.filter(especialidad='').prefetch_related(
        'profesional__especialidades',
    )
    for turno in turnos.iterator(chunk_size=500):
        nombres = [e.nombre for e in turno.profesional.especialidades.all()]
        if not nombres:
            continue

        valor = ', '.join(nombres)[:50]
        turno.especialidad = valor
        turno.save(update_fields=['especialidad'])

        schema_editor.execute(
            f'DELETE FROM "{TABLA_RESPALDO}" WHERE "turno_id" = %s',
            [turno.pk],
        )
        schema_editor.execute(
            f'INSERT INTO "{TABLA_RESPALDO}" '
            '("turno_id", "valor_completado") VALUES (%s, %s)',
            [turno.pk, valor],
        )


def revertir_especialidades(apps, schema_editor):
    """Restaura los turnos que esta migración completó."""
    Turno = apps.get_model('turnos', 'Turno')

    tablas = schema_editor.connection.introspection.table_names()
    if TABLA_RESPALDO not in tablas:
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f'SELECT "turno_id", "valor_completado" FROM "{TABLA_RESPALDO}"'
        )
        respaldos = cursor.fetchall()

    for turno_id, valor in respaldos:
        # Solo limpiamos si el turno conserva exactamente el texto que agregó
        # esta migración. Si fue editado después, se respeta el dato nuevo.
        Turno.objects.filter(pk=turno_id, especialidad=valor).update(
            especialidad=''
        )

    schema_editor.execute(f'DROP TABLE IF EXISTS "{TABLA_RESPALDO}"')


class Migration(migrations.Migration):

    dependencies = [
        ('turnos', '0001_initial'),
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
