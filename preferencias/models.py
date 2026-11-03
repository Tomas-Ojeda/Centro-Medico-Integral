from django.conf import settings
from django.db import models


PALETAS = [
    ('predeterminado', 'Consultorios'),
    ('dorado', 'Dorado'),
    ('menta', 'Menta'),
    ('lavanda', 'Lavanda'),
    ('durazno', 'Durazno'),
    ('cielo', 'Cielo'),
    ('rosa', 'Rosa'),
]
PALETAS_POR_CLAVE = dict(PALETAS)

# Color representativo de cada paleta para el selector del menú.
MUESTRAS_PALETAS = {
    'predeterminado': '#2f6fe0',
    'dorado': '#c9a84c',
    'menta': '#6cc3a8',
    'lavanda': '#a99be0',
    'durazno': '#f0a98a',
    'cielo': '#7db7e8',
    'rosa': '#e8a0b4',
}


def paletas_disponibles():
    """Lista lista para el selector de paletas de base.html."""
    return [
        {
            'clave': clave,
            'nombre': nombre,
            'muestra': MUESTRAS_PALETAS[clave],
        }
        for clave, nombre in PALETAS
    ]


class PreferenciaUsuario(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='preferencia',
    )
    paleta = models.CharField(
        max_length=20,
        choices=PALETAS,
        default='predeterminado',
    )

    class Meta:
        verbose_name = 'Preferencia de usuario'
        verbose_name_plural = 'Preferencias de usuario'

    def __str__(self):
        return f'{self.usuario} — {self.get_paleta_display()}'
