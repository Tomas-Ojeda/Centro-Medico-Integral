from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from pacientes.models import Paciente
from profesionales.models import Profesional
from turnos.models import (
    EstadoSolicitud,
    Plazo,
    SolicitudTurno,
    calcular_fecha_sugerida,
)


class EstadoDerivacion(models.TextChoices):
    PENDIENTE = 'pendiente', 'Pendiente'
    VISTA = 'vista', 'Vista'
    CANCELADA = 'cancelada', 'Cancelada'


class Derivacion(models.Model):
    """Derivación de un paciente entre dos profesionales.

    La derivación pendiente o vista también habilita al profesional destino
    a acceder a la ficha del paciente (ver ``PacienteQuerySet.atendidos_por``).
    Al crearse, genera una solicitud de turno para que Recepción agende la
    consulta con el profesional destino.
    """

    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.CASCADE,
        related_name='derivaciones',
        verbose_name='Paciente',
    )
    profesional_origen = models.ForeignKey(
        Profesional,
        on_delete=models.PROTECT,
        related_name='derivaciones_enviadas',
        verbose_name='Profesional de origen',
    )
    profesional_destino = models.ForeignKey(
        Profesional,
        on_delete=models.PROTECT,
        related_name='derivaciones_recibidas',
        verbose_name='Profesional de destino',
    )
    motivo = models.TextField(verbose_name='Motivo')
    estado = models.CharField(
        max_length=15,
        choices=EstadoDerivacion.choices,
        default=EstadoDerivacion.PENDIENTE,
        verbose_name='Estado',
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='derivaciones_creadas',
        verbose_name='Creada por',
    )
    creado = models.DateTimeField(auto_now_add=True, verbose_name='Creada')
    vista_en = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Vista en',
    )
    solicitud_turno = models.ForeignKey(
        SolicitudTurno,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='derivaciones',
        verbose_name='Solicitud de turno',
    )

    class Meta:
        ordering = ['-creado']
        verbose_name = 'Derivación'
        verbose_name_plural = 'Derivaciones'
        indexes = [
            models.Index(
                fields=['profesional_destino', 'estado'],
                name='deriv_destino_estado_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(profesional_origen=F('profesional_destino')),
                name='deriv_origen_distinto_destino',
            ),
        ]

    def __str__(self):
        return (
            f'{self.paciente} — {self.profesional_origen} → '
            f'{self.profesional_destino} ({self.get_estado_display()})'
        )

    def clean(self):
        super().clean()
        if (
            self.profesional_origen_id
            and self.profesional_destino_id
            and self.profesional_origen_id == self.profesional_destino_id
        ):
            raise ValidationError({
                'profesional_destino': (
                    'El profesional de destino debe ser distinto del '
                    'profesional de origen.'
                ),
            })

    @property
    def esta_pendiente(self):
        return self.estado == EstadoDerivacion.PENDIENTE

    @property
    def esta_vista(self):
        return self.estado == EstadoDerivacion.VISTA

    @property
    def esta_cancelada(self):
        return self.estado == EstadoDerivacion.CANCELADA

    @property
    def nota_solicitud(self):
        return f'Derivado por {self.profesional_origen}: {self.motivo}'

    def crear_solicitud_turno(self):
        """Crea (o actualiza) la solicitud de turno para el destino.

        Recepción la verá en "Turnos por agendar". Si el destino ya tenía una
        solicitud pendiente para el paciente se reutiliza, respetando la
        restricción de unicidad de la Tarea I.
        """
        if self.solicitud_turno_id:
            return self.solicitud_turno

        solicitud, _ = SolicitudTurno.objects.update_or_create(
            paciente=self.paciente,
            profesional=self.profesional_destino,
            estado=EstadoSolicitud.PENDIENTE,
            defaults={
                'solicitado_por': self.creado_por,
                'plazo': Plazo.UNA_SEMANA,
                'fecha_sugerida': calcular_fecha_sugerida(Plazo.UNA_SEMANA),
                'nota': self.nota_solicitud,
                'turno': None,
                'resuelto_en': None,
                'resuelto_por': None,
                'motivo_resolucion': '',
            },
        )
        self.solicitud_turno = solicitud
        self.save(update_fields=['solicitud_turno'])
        return solicitud
