from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

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
