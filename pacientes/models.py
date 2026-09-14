from django.db import models
from django.utils import timezone


class ObraSocial(models.TextChoices):
    OSDE = 'OSDE', 'OSDE'
    OSEP = 'OSEP', 'OSEP'
    SWISS_MEDICAL = 'Swiss Medical', 'Swiss Medical'
    MEDICUS = 'Medicus', 'Medicus'
    GALENO = 'Galeno', 'Galeno'
    IOMA = 'IOMA', 'IOMA'
    PARTICULAR = 'Particular', 'Particular'
    OTRO = 'Otro', 'Otro'


class Paciente(models.Model):
    numero_socio = models.CharField(max_length=20, unique=True, blank=True, null=True)
    dni = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    fecha_nacimiento = models.DateField()
    telefono = models.CharField(max_length=25, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    obra_social = models.CharField(
        max_length=30,
        choices=ObraSocial.choices,
        default=ObraSocial.PARTICULAR
    )
    fecha_alta = models.DateField(auto_now_add=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['apellido', 'nombre']
        verbose_name = 'Paciente'
        verbose_name_plural = 'Pacientes'

    def __str__(self):
        return f"{self.apellido}, {self.nombre}"

    @property
    def nombre_completo(self):
        return f"{self.apellido}, {self.nombre}"

    @property
    def iniciales(self):
        return f"{self.nombre[0]}{self.apellido[0]}".upper()

    @property
    def edad(self):
        today = timezone.now().date()
        born = self.fecha_nacimiento
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
