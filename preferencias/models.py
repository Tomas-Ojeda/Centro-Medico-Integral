from django.conf import settings
from django.db import models


PALETAS = [
    ('predeterminado', 'Predeterminado'),
    ('menta', 'Menta'),
    ('lavanda', 'Lavanda'),
    ('durazno', 'Durazno'),
    ('cielo', 'Cielo'),
    ('rosa', 'Rosa'),
]
PALETAS_POR_CLAVE = dict(PALETAS)


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
