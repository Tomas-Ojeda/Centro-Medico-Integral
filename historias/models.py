import os
import uuid
import magic
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from pacientes.models import Paciente
from profesionales.models import Profesional


def ruta_adjunto_aleatoria(instance, filename):
    """Genera una ruta aleatoria con UUID para el archivo adjunto."""
    ext = os.path.splitext(filename)[1].lower()
    nombre_uuid = uuid.uuid4().hex
    return f'historias_clinicas/{nombre_uuid}{ext}'


def validar_tipo_mime(archivo):
    """Valida que el tipo MIME real del archivo sea permitido."""
    MIME_PERMITIDOS = {
        'application/pdf': '.pdf',
        'image/jpeg': '.jpg',
        'image/png': '.png',
    }
    try:
        mime = magic.from_buffer(archivo.read(2048), mime=True)
        archivo.seek(0)  # Rewind para no afectar la lectura posterior
    except Exception:
        raise ValidationError('No se pudo validar el tipo de archivo.')

    if mime not in MIME_PERMITIDOS:
        raise ValidationError(
            f'Tipo de archivo no permitido: {mime}. '
            f'Solo se permiten: PDF, JPG, PNG.'
        )


def validar_tamano_archivo(archivo):
    """Valida que el archivo no supere 10 MB."""
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB
    if archivo.size > MAX_SIZE:
        raise ValidationError(
            f'El archivo supera el límite de 10 MB. '
            f'Tamaño actual: {archivo.size / (1024*1024):.1f} MB.'
        )


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
        upload_to=ruta_adjunto_aleatoria,
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png']),
            validar_tipo_mime,
            validar_tamano_archivo,
        ],
    )
    es_mas_reciente = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_hora']
        verbose_name = 'Consulta'
        verbose_name_plural = 'Historial Clínico'

    def __str__(self):
        return f'Consulta de {self.paciente} — {self.fecha_hora.strftime("%d/%m/%Y")}'

    @property
    def especialidad_mostrar(self):
        """Texto histórico o, si está vacío, las especialidades actuales del profesional."""
        if self.especialidad:
            return self.especialidad
        return ', '.join(e.nombre for e in self.profesional.especialidades.all())

    def save(self, *args, **kwargs):
        if not self.especialidad and self.profesional_id:
            nombres = [e.nombre for e in self.profesional.especialidades.all()]
            if nombres:
                self.especialidad = ', '.join(nombres)[:50]
        super().save(*args, **kwargs)
        # Mark this as most recent for the patient
        Consulta.objects.filter(paciente=self.paciente).exclude(pk=self.pk).update(es_mas_reciente=False)
        Consulta.objects.filter(pk=self.pk).update(es_mas_reciente=True)


class CampoAdicional(models.Model):
    """Campos personalizables que el usuario puede crear para las consultas."""
    nombre = models.CharField(max_length=100, verbose_name='Nombre del campo')
    tipo = models.CharField(
        max_length=20,
        choices=[
            ('texto', 'Texto'),
            ('numero', 'Número'),
            ('fecha', 'Fecha'),
            ('opciones', 'Opciones'),
        ],
        default='texto',
        verbose_name='Tipo de campo'
    )
    opciones = models.TextField(
        blank=True,
        help_text='Para tipo "opciones", separar valores con comas',
        verbose_name='Opciones'
    )
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Campo Adicional'
        verbose_name_plural = 'Campos Adicionales'

    def __str__(self):
        return self.nombre


class ValorCampoAdicional(models.Model):
    """Valores de campos adicionales para cada consulta."""
    consulta = models.ForeignKey(
        Consulta, on_delete=models.CASCADE, related_name='campos_adicionales'
    )
    campo = models.ForeignKey(
        CampoAdicional, on_delete=models.CASCADE, related_name='valores'
    )
    valor = models.TextField(blank=True, verbose_name='Valor')

    class Meta:
        unique_together = ['consulta', 'campo']
        verbose_name = 'Valor de Campo Adicional'
        verbose_name_plural = 'Valores de Campos Adicionales'

    def __str__(self):
        return f'{self.campo.nombre}: {self.valor[:50]}'
