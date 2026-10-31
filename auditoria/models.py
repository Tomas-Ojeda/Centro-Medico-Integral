from django.db import models
from django.contrib.auth.models import User


class LogAcceso(models.Model):
    """Registro de auditoría de accesos para cumplir con la Ley 25326."""

    class Accion(models.TextChoices):
        VER = 'ver', 'Ver'
        CREAR = 'crear', 'Crear'
        EDITAR = 'editar', 'Editar'
        BORRAR = 'borrar', 'Borrar'
        DESCARGAR = 'descargar', 'Descargar'
        EXPORTAR = 'exportar', 'Exportar'
        IMPORTAR = 'importar', 'Importar'
        LOGIN = 'login', 'Login'
        LOGIN_FALLIDO = 'login_fallido', 'Login fallido'
        LOGOUT = 'logout', 'Logout'

    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs_acceso',
        verbose_name='Usuario'
    )
    fecha_hora = models.DateTimeField(auto_now_add=True, verbose_name='Fecha y hora')
    accion = models.CharField(
        max_length=20,
        choices=Accion.choices,
        verbose_name='Acción'
    )
    modelo = models.CharField(max_length=100, blank=True, verbose_name='Modelo')
    objeto_id = models.PositiveIntegerField(null=True, blank=True, verbose_name='ID del objeto')
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')
    user_agent = models.TextField(blank=True, verbose_name='User-Agent')
    detalle = models.TextField(
        blank=True,
        verbose_name='Detalle',
        help_text='Valores anteriores y nuevos cuando corresponde.',
    )

    class Meta:
        ordering = ['-fecha_hora']
        verbose_name = 'Log de Acceso'
        verbose_name_plural = 'Logs de Acceso'

    def __str__(self):
        usuario = self.usuario.username if self.usuario else 'Anónimo'
        return f'{usuario} - {self.accion} - {self.fecha_hora.strftime("%d/%m/%Y %H:%M")}'
