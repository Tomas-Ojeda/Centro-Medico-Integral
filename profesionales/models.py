from django.conf import settings
from django.db import models


class Especialidad(models.Model):
    nombre = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Especialidad'
        verbose_name_plural = 'Especialidades'

    def __str__(self):
        return self.nombre


class Profesional(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    dni = models.CharField(max_length=10, unique=True)
    matricula_nacional = models.CharField(max_length=20, blank=True, null=True)
    matricula_provincial = models.CharField(max_length=20, blank=True)
    especialidades = models.ManyToManyField('Especialidad', blank=True, related_name='profesionales')
    telefono = models.CharField(max_length=25, blank=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    foto = models.ImageField(upload_to='profesionales/', blank=True, null=True)
    fecha_ingreso = models.DateField()
    activo = models.BooleanField(default=True)
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='profesional',
        verbose_name='Usuario de acceso',
        help_text='Vinculación con el usuario de Django. Se administra solo desde /admin.',
    )

    class Meta:
        ordering = ['apellido', 'nombre']
        verbose_name = 'Profesional'
        verbose_name_plural = 'Profesionales'

    def __str__(self):
        return f"Dr/a. {self.apellido}, {self.nombre}"

    @property
    def nombre_completo(self):
        return f"{self.apellido}, {self.nombre}"

    @property
    def iniciales(self):
        return f"{self.nombre[0]}{self.apellido[0]}".upper()
