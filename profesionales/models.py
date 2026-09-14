from django.db import models


class Especialidad(models.TextChoices):
    CLINICA = 'Clínica Médica', 'Clínica Médica'
    CARDIOLOGIA = 'Cardiología', 'Cardiología'
    PEDIATRIA = 'Pediatría', 'Pediatría'
    GINECOLOGIA = 'Ginecología', 'Ginecología'
    NEUROLOGIA = 'Neurología', 'Neurología'
    TRAUMATOLOGIA = 'Traumatología', 'Traumatología'
    KINESIOLOGIA = 'Kinesiología', 'Kinesiología'
    PSICOLOGIA = 'Psicología', 'Psicología'
    ODONTOLOGIA = 'Odontología', 'Odontología'
    DERMATOLOGIA = 'Dermatología', 'Dermatología'
    OFTALMOLOGIA = 'Oftalmología', 'Oftalmología'
    OTRO = 'Otro', 'Otro'


class Profesional(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    dni = models.CharField(max_length=10, unique=True)
    matricula_nacional = models.CharField(max_length=20, unique=True)
    matricula_provincial = models.CharField(max_length=20, blank=True)
    especialidad = models.CharField(max_length=50, choices=Especialidad.choices)
    telefono = models.CharField(max_length=25, blank=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    foto = models.ImageField(upload_to='profesionales/', blank=True, null=True)
    fecha_ingreso = models.DateField()
    activo = models.BooleanField(default=True)

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
