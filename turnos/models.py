from django.db import models
from pacientes.models import Paciente
from profesionales.models import Profesional


class EstadoTurno(models.TextChoices):
    PENDIENTE = 'pendiente', 'Pendiente'
    CONFIRMADO = 'confirmado', 'Confirmado'
    REALIZADO = 'realizado', 'Realizado'
    CANCELADO = 'cancelado', 'Cancelado'
    AUSENTE = 'ausente', 'Ausente'


class Turno(models.Model):
    paciente = models.ForeignKey(
        Paciente, on_delete=models.CASCADE, related_name='turnos'
    )
    profesional = models.ForeignKey(
        Profesional, on_delete=models.PROTECT, related_name='turnos'
    )
    fecha_hora = models.DateTimeField()
    especialidad = models.CharField(max_length=50, blank=True)
    motivo = models.TextField(blank=True)
    estado = models.CharField(
        max_length=15,
        choices=EstadoTurno.choices,
        default=EstadoTurno.PENDIENTE
    )
    observaciones = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['fecha_hora']
        verbose_name = 'Turno'
        verbose_name_plural = 'Turnos'

    def __str__(self):
        return f"{self.paciente} - {self.profesional} ({self.fecha_hora.strftime('%d/%m/%Y %H:%M')})"

    def save(self, *args, **kwargs):
        if not self.especialidad and self.profesional_id:
            self.especialidad = self.profesional.especialidad
        super().save(*args, **kwargs)
