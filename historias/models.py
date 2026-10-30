import io
import os
import uuid

import magic
from PIL import Image, ImageOps, UnidentifiedImageError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import FileExtensionValidator, MaxLengthValidator
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from pacientes.models import Paciente
from profesionales.models import Profesional


EXTENSIONES_ADJUNTO = ['pdf', 'jpg', 'jpeg', 'png']
EXTENSIONES_IMAGEN = {'.jpg', '.jpeg', '.png'}


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


def validar_imagen_adjunto(archivo):
    """Verifica que una imagen JPG/PNG pueda abrirse con Pillow.

    Los PDF no se procesan con Pillow: se conservan tal cual.
    """
    extension = os.path.splitext(getattr(archivo, 'name', ''))[1].lower()
    if extension not in EXTENSIONES_IMAGEN:
        return

    try:
        archivo.seek(0)
        with Image.open(archivo) as imagen:
            imagen.verify()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
    ) as exc:
        raise ValidationError(
            'El archivo no es una imagen válida o está dañado.'
        ) from exc
    finally:
        try:
            archivo.seek(0)
        except (AttributeError, OSError):
            pass


def procesar_archivo_adjunto(archivo):
    """Normaliza imágenes antes de guardarlas en el storage.

    - Aplica la orientación EXIF.
    - Elimina los metadatos EXIF (incluida la ubicación GPS).
    - Reduce el lado mayor a 2000 px.
    - Guarda JPG con calidad 85 y PNG sin alterar su transparencia.
    - Los PDF se devuelven sin cambios.
    """
    extension = os.path.splitext(getattr(archivo, 'name', ''))[1].lower()
    if extension not in EXTENSIONES_IMAGEN:
        return archivo

    try:
        archivo.seek(0)
        with Image.open(archivo) as original:
            imagen = ImageOps.exif_transpose(original)
            imagen.thumbnail((2000, 2000), Image.Resampling.LANCZOS)

            # Quitar metadatos antes de volver a codificar.
            for clave in ('exif', 'icc_profile', 'xmp', 'XML:com.adobe.xmp'):
                imagen.info.pop(clave, None)

            salida = io.BytesIO()
            if extension in {'.jpg', '.jpeg'}:
                if imagen.mode in ('RGBA', 'LA') or (
                    imagen.mode == 'P' and 'transparency' in imagen.info
                ):
                    imagen = imagen.convert('RGBA')
                    fondo = Image.new('RGB', imagen.size, (255, 255, 255))
                    fondo.paste(imagen, mask=imagen.getchannel('A'))
                    imagen = fondo
                elif imagen.mode != 'RGB':
                    imagen = imagen.convert('RGB')
                imagen.save(
                    salida,
                    format='JPEG',
                    quality=85,
                    optimize=True,
                )
            else:
                if imagen.mode == 'CMYK':
                    imagen = imagen.convert('RGB')
                elif imagen.mode not in ('RGB', 'RGBA', 'L', 'LA'):
                    imagen = imagen.convert('RGBA')
                imagen.save(salida, format='PNG', optimize=True)

        salida.seek(0)
        return ContentFile(
            salida.read(),
            name=os.path.basename(archivo.name),
        )
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
    ) as exc:
        raise ValidationError(
            'No se pudo procesar la imagen adjunta.'
        ) from exc
    finally:
        try:
            archivo.seek(0)
        except (AttributeError, OSError):
            pass


VALIDADORES_ADJUNTO = [
    FileExtensionValidator(allowed_extensions=EXTENSIONES_ADJUNTO),
    validar_tipo_mime,
    validar_tamano_archivo,
]
VALIDADORES_ADJUNTO_HISTORIA = VALIDADORES_ADJUNTO + [validar_imagen_adjunto]


def validar_archivo_adjunto(archivo):
    """Ejecuta todas las validaciones de un adjunto de historia clínica."""
    for validador in VALIDADORES_ADJUNTO_HISTORIA:
        validador(archivo)


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
        validators=VALIDADORES_ADJUNTO,
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


class AdjuntoHistoria(models.Model):
    """Archivo de historia clínica del paciente (foto o PDF)."""

    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.CASCADE,
        related_name='adjuntos_historia',
        verbose_name='Paciente',
    )
    turno = models.ForeignKey(
        'turnos.Turno',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='adjuntos_historia',
        verbose_name='Turno',
    )
    archivo = models.FileField(
        upload_to=ruta_adjunto_aleatoria,
        validators=VALIDADORES_ADJUNTO_HISTORIA,
        verbose_name='Archivo',
    )
    descripcion = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Descripción',
    )
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='adjuntos_historia_subidos',
        verbose_name='Subido por',
    )
    creado = models.DateTimeField(auto_now_add=True, verbose_name='Creado')

    class Meta:
        ordering = ['-creado']
        verbose_name = 'Adjunto de historia clínica'
        verbose_name_plural = 'Adjuntos de historia clínica'

    def __str__(self):
        return f'Adjunto de {self.paciente} — {self.creado:%d/%m/%Y}'

    @property
    def extension(self):
        return os.path.splitext(self.archivo.name)[1].lower()

    @property
    def es_imagen(self):
        return self.extension in EXTENSIONES_IMAGEN

    @property
    def es_pdf(self):
        return self.extension == '.pdf'

    @property
    def nombre_archivo(self):
        return os.path.basename(self.archivo.name)

    def save(self, *args, **kwargs):
        if self.archivo and not getattr(self.archivo, '_committed', True):
            archivo_procesado = procesar_archivo_adjunto(self.archivo)
            if archivo_procesado is not self.archivo:
                self.archivo = archivo_procesado
        super().save(*args, **kwargs)


@receiver(post_delete, sender=AdjuntoHistoria)
def eliminar_archivo_adjunto_historia(sender, instance, **kwargs):
    """Borra el archivo del storage cuando se elimina el registro."""
    if instance.archivo:
        instance.archivo.delete(save=False)


class CampoAdicional(models.Model):
    """Campos personalizables que el usuario puede crear para las consultas.

    ``profesional`` es el dueño del campo. Cuando es ``NULL`` el campo es
    general y lo ven todos los profesionales.
    """
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
    profesional = models.ForeignKey(
        Profesional,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campos_adicionales',
        verbose_name='Profesional',
        help_text='Vacío = campo general visible para todos.',
    )
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Campo Adicional'
        verbose_name_plural = 'Campos Adicionales'
        indexes = [
            models.Index(
                fields=['activo', 'profesional'],
                name='hist_campo_act_prof_idx',
            ),
        ]

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


class NotaClinica(models.Model):
    """Anotación clínica libre, con fecha y autor."""

    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.CASCADE,
        related_name='notas',
        verbose_name='Paciente',
    )
    consulta = models.ForeignKey(
        Consulta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notas',
        verbose_name='Consulta',
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notas_clinicas',
        verbose_name='Autor',
    )
    profesional = models.ForeignKey(
        Profesional,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notas_clinicas',
        verbose_name='Profesional',
    )
    texto = models.TextField(
        max_length=10000,
        validators=[MaxLengthValidator(10000)],
        verbose_name='Anotación',
    )
    creado = models.DateTimeField(auto_now_add=True, verbose_name='Creada')
    editado_en = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Editada en',
    )

    class Meta:
        ordering = ['-creado']
        verbose_name = 'Anotación'
        verbose_name_plural = 'Anotaciones'
        indexes = [
            models.Index(
                fields=['paciente', 'creado'],
                name='hist_nota_pac_creado_idx',
            ),
        ]

    def __str__(self):
        return f'Anotación de {self.paciente} — {self.creado:%d/%m/%Y %H:%M}'

    def save(self, *args, **kwargs):
        if not self.profesional_id and self.autor_id:
            self.profesional = Profesional.objects.filter(
                usuario_id=self.autor_id
            ).first()
        super().save(*args, **kwargs)

    @property
    def autor_nombre(self):
        if not self.autor_id:
            return 'Usuario eliminado'
        return self.autor.get_full_name() or self.autor.username

    @property
    def especialidad_mostrar(self):
        if not self.profesional_id:
            return ''
        return ', '.join(
            especialidad.nombre
            for especialidad in self.profesional.especialidades.all()
        )
