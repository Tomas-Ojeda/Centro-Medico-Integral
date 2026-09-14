from django.db import models
from pacientes.models import Paciente
from profesionales.models import Profesional


class Consulta(models.Model):
    paciente = models.ForeignKey(
        Paciente, on_delete=models.CASCADE, related_name='consultas'
    )
    profesional = models.ForeignKey(
        Profesional, on_delete=models.PROTECT, related_name='consultas'
    )
    fecha_hora = models.DateTimeField()
    especialidad = models.CharField(max_length=50, blank=True)
    motivo = models.TextField(blank=True, verbose_name='Motivo de consulta')
    diagnostico = models.TextField(verbose_name='Diagnóstico')
    evolucion = models.TextField(blank=True, verbose_name='Evolución / Observaciones')
    tratamiento = models.TextField(blank=True, verbose_name='Tratamiento indicado')
    archivo_adjunto = models.FileField(
        upload_to='historias_clinicas/%Y/%m/', blank=True, null=True
    )
    es_mas_reciente = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_hora']
        verbose_name = 'Consulta'
        verbose_name_plural = 'Historial Clínico'

    def __str__(self):
        return f'Consulta de {self.paciente} — {self.fecha_hora.strftime("%d/%m/%Y")}'

    def save(self, *args, **kwargs):
        if not self.especialidad and self.profesional_id:
            self.especialidad = self.profesional.especialidad
        super().save(*args, **kwargs)
        # Mark this as most recent for the patient
        Consulta.objects.filter(paciente=self.paciente).exclude(pk=self.pk).update(es_mas_reciente=False)
        Consulta.objects.filter(pk=self.pk).update(es_mas_reciente=True)
