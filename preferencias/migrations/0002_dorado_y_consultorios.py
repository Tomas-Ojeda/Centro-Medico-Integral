from django.db import migrations, models


def migrar_predeterminado_a_dorado(apps, schema_editor):
    """Conserva el aspecto anterior de quienes usaban la paleta dorada."""
    PreferenciaUsuario = apps.get_model('preferencias', 'PreferenciaUsuario')
    PreferenciaUsuario.objects.filter(paleta='predeterminado').update(
        paleta='dorado'
    )


def migrar_dorado_a_predeterminado(apps, schema_editor):
    PreferenciaUsuario = apps.get_model('preferencias', 'PreferenciaUsuario')
    PreferenciaUsuario.objects.filter(paleta='dorado').update(
        paleta='predeterminado'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('preferencias', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='preferenciausuario',
            name='paleta',
            field=models.CharField(
                choices=[
                    ('predeterminado', 'Consultorios'),
                    ('dorado', 'Dorado'),
                    ('menta', 'Menta'),
                    ('lavanda', 'Lavanda'),
                    ('durazno', 'Durazno'),
                    ('cielo', 'Cielo'),
                    ('rosa', 'Rosa'),
                ],
                default='predeterminado',
                max_length=20,
            ),
        ),
        migrations.RunPython(
            migrar_predeterminado_a_dorado,
            migrar_dorado_a_predeterminado,
        ),
    ]
