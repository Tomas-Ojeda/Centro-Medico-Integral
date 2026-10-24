from django.db import migrations

TABLA_RESPALDO = '_migracion_roles_recepcion'


def crear_grupos(apps, schema_editor):
    """Crea los grupos y conserva el acceso de los usuarios existentes.

    Todos los usuarios no superusuarios existentes quedan en Recepcion para
    que el deploy no les quite el acceso que tenían antes de los roles.
    Guardamos en una tabla de respaldo solo los usuarios agregados por esta
    migración, para poder revertir sin quitar asignaciones manuales.
    """
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')

    recepcion, _ = Group.objects.get_or_create(name='Recepcion')
    Group.objects.get_or_create(name='Profesional')

    schema_editor.execute(
        f'CREATE TABLE IF NOT EXISTS "{TABLA_RESPALDO}" ('
        '"user_id" integer PRIMARY KEY)'
    )

    usuarios = User.objects.filter(is_superuser=False).exclude(
        groups__name='Recepcion'
    ).distinct()
    for usuario in usuarios.iterator(chunk_size=500):
        recepcion.user_set.add(usuario)
        schema_editor.execute(
            f'DELETE FROM "{TABLA_RESPALDO}" WHERE "user_id" = %s',
            [usuario.pk],
        )
        schema_editor.execute(
            f'INSERT INTO "{TABLA_RESPALDO}" ("user_id") VALUES (%s)',
            [usuario.pk],
        )


def revertir_grupos(apps, schema_editor):
    """Revierte solo las asignaciones automáticas de esta migración.

    No eliminamos los grupos ni las asignaciones manuales hechas después del
    deploy. Si la tabla de respaldo no existe, no hay nada que revertir.
    """
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')

    tablas = schema_editor.connection.introspection.table_names()
    if TABLA_RESPALDO not in tablas:
        return

    recepcion = Group.objects.filter(name='Recepcion').first()
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f'SELECT "user_id" FROM "{TABLA_RESPALDO}"')
        ids = [fila[0] for fila in cursor.fetchall()]

    if recepcion is not None and ids:
        recepcion.user_set.remove(*User.objects.filter(pk__in=ids))

    schema_editor.execute(f'DROP TABLE IF EXISTS "{TABLA_RESPALDO}"')


class Migration(migrations.Migration):

    dependencies = [
        ('profesionales', '0003_profesional_usuario'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(crear_grupos, revertir_grupos),
    ]
