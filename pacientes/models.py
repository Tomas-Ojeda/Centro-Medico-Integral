from django.db import models
from django.db.models import Q
from django.utils import timezone


class PacienteQuerySet(models.QuerySet):
    def atendidos_por(self, profesional):
        """Pacientes vinculados a ese profesional.

        Incluye turnos, consultas y derivaciones recibidas pendientes o
        vistas. Una derivación cancelada no otorga acceso por sí sola.
        """
        if profesional is None:
            return self.none()

        # Import local para evitar un ciclo de importación entre apps.
        from derivaciones.models import EstadoDerivacion

        return self.filter(
            Q(turnos__profesional=profesional)
            | Q(consultas__profesional=profesional)
            | Q(
                derivaciones__profesional_destino=profesional,
                derivaciones__estado__in=[
                    EstadoDerivacion.PENDIENTE,
                    EstadoDerivacion.VISTA,
                ],
            )
        ).distinct()


class PacienteManager(models.Manager.from_queryset(PacienteQuerySet)):
    pass


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
    objects = PacienteManager()

    numero_socio = models.CharField(max_length=20, unique=True, blank=True, null=True)
    dni = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    fecha_nacimiento = models.DateField()
    telefono = models.CharField(max_length=25, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    obra_social = models.CharField(max_length=50, blank=True, default='Particular')
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
