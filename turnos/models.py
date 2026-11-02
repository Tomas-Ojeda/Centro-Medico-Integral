import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from pacientes.models import Paciente
from profesionales.models import Profesional


class EstadoTurno(models.TextChoices):
    PENDIENTE = 'pendiente', 'Pendiente'
    CONFIRMADO = 'confirmado', 'Confirmado'
    REALIZADO = 'realizado', 'Realizado'
    CANCELADO = 'cancelado', 'Cancelado'
    AUSENTE = 'ausente', 'Ausente'


class FormaPago(models.TextChoices):
    EFECTIVO = 'efectivo', 'Efectivo'
    TRANSFERENCIA = 'transferencia', 'Transferencia'
    COBERTURA = 'cobertura', 'Obra social / sin cargo'


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

    # ─── Registro interno de pago (no fiscal) ───────────────────
    forma_pago = models.CharField(
        max_length=20,
        choices=FormaPago.choices,
        blank=True,
        verbose_name='Forma de pago',
    )
    monto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Monto',
    )
    fecha_pago = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Fecha de pago',
    )
    pago_registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pagos_registrados',
        verbose_name='Pago registrado por',
    )

    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['fecha_hora']
        verbose_name = 'Turno'
        verbose_name_plural = 'Turnos'

    def __str__(self):
        return f"{self.paciente} - {self.profesional} ({self.fecha_hora.strftime('%d/%m/%Y %H:%M')})"

    @property
    def especialidad_actual(self):
        """Especialidades vigentes del profesional, sin usar el texto copiado."""
        return ', '.join(e.nombre for e in self.profesional.especialidades.all())

    @property
    def pago_registrado(self):
        return self.fecha_pago is not None

    @property
    def permite_registrar_pago(self):
        """No se cobra un turno cancelado ni un ausente."""
        return self.estado not in (
            EstadoTurno.CANCELADO,
            EstadoTurno.AUSENTE,
        )

    @property
    def pago_texto(self):
        from .utils import texto_pago

        return texto_pago(self.forma_pago, self.monto)

    def save(self, *args, **kwargs):
        if not self.especialidad and self.profesional_id:
            especialidades = self.profesional.especialidades.all()
            if especialidades.exists():
                self.especialidad = ', '.join([e.nombre for e in especialidades])[:50]
        super().save(*args, **kwargs)


class Plazo(models.TextChoices):
    UNA_SEMANA = '1_semana', '1 semana'
    QUINCE_DIAS = '15_dias', '15 días'
    UN_MES = '1_mes', '1 mes'
    DOS_MESES = '2_meses', '2 meses'
    TRES_MESES = '3_meses', '3 meses'
    FECHA_EXACTA = 'fecha_exacta', 'Fecha exacta'


class EstadoSolicitud(models.TextChoices):
    PENDIENTE = 'pendiente', 'Pendiente'
    AGENDADA = 'agendada', 'Agendada'
    DESCARTADA = 'descartada', 'Descartada'


def sumar_meses(fecha, meses):
    """Suma meses a una fecha ajustando el día al último del mes destino."""
    indice = fecha.month - 1 + meses
    anio = fecha.year + indice // 12
    mes = indice % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def calcular_fecha_sugerida(plazo, fecha_exacta=None, base=None):
    """Calcula la fecha sugerida a partir del plazo elegido.

    ``fecha_exacta`` solo se usa cuando el plazo es ``FECHA_EXACTA``.
    """
    base = base or timezone.localdate()

    if plazo == Plazo.FECHA_EXACTA:
        return fecha_exacta
    if plazo == Plazo.UNA_SEMANA:
        return base + timedelta(days=7)
    if plazo == Plazo.QUINCE_DIAS:
        return base + timedelta(days=15)
    if plazo == Plazo.UN_MES:
        return sumar_meses(base, 1)
    if plazo == Plazo.DOS_MESES:
        return sumar_meses(base, 2)
    if plazo == Plazo.TRES_MESES:
        return sumar_meses(base, 3)
    return base


class SolicitudTurno(models.Model):
    """Próximo turno pedido por un profesional para un paciente.

    Funciona como cola de trabajo para Recepción: mientras está pendiente
    aparece en "Turnos por agendar". Al crear el turno desde la solicitud,
    esta queda enlazada y pasa a ``agendada``.
    """

    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.CASCADE,
        related_name='solicitudes_turno',
        verbose_name='Paciente',
    )
    profesional = models.ForeignKey(
        Profesional,
        on_delete=models.PROTECT,
        related_name='solicitudes_turno',
        verbose_name='Profesional',
    )
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitudes_turno_solicitadas',
        verbose_name='Solicitado por',
    )
    plazo = models.CharField(
        max_length=15,
        choices=Plazo.choices,
        default=Plazo.UNA_SEMANA,
        verbose_name='Plazo',
    )
    fecha_sugerida = models.DateField(verbose_name='Fecha sugerida')
    nota = models.TextField(blank=True, verbose_name='Nota')
    estado = models.CharField(
        max_length=15,
        choices=EstadoSolicitud.choices,
        default=EstadoSolicitud.PENDIENTE,
        verbose_name='Estado',
    )
    turno = models.ForeignKey(
        Turno,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitudes_origen',
        verbose_name='Turno',
    )
    creado = models.DateTimeField(auto_now_add=True, verbose_name='Creada')
    resuelto_en = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Resuelta en',
    )
    resuelto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitudes_turno_resueltas',
        verbose_name='Resuelta por',
    )
    motivo_resolucion = models.TextField(
        blank=True,
        verbose_name='Motivo de la resolución',
        help_text='Motivo opcional al descartar la solicitud.',
    )

    class Meta:
        ordering = ['fecha_sugerida', 'creado']
        verbose_name = 'Solicitud de turno'
        verbose_name_plural = 'Solicitudes de turno'
        indexes = [
            models.Index(
                fields=['estado', 'fecha_sugerida'],
                name='turnos_sol_estado_fecha_idx',
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['paciente', 'profesional'],
                condition=Q(estado=EstadoSolicitud.PENDIENTE),
                name='turnos_sol_pendiente_unica',
            ),
        ]

    def __str__(self):
        return (
            f'{self.paciente} - {self.profesional} '
            f'({self.fecha_sugerida:%d/%m/%Y})'
        )

    @property
    def esta_vencida(self):
        return (
            self.estado == EstadoSolicitud.PENDIENTE
            and self.fecha_sugerida < timezone.localdate()
        )

    def save(self, *args, **kwargs):
        if not self.fecha_sugerida and self.plazo:
            self.fecha_sugerida = calcular_fecha_sugerida(self.plazo)
        super().save(*args, **kwargs)
