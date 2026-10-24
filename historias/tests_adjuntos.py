import io
import os
import shutil
import tempfile
from datetime import date, time

from PIL import Image
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from auditoria.models import LogAcceso
from consultorio_salto.permisos import GRUPO_PROFESIONAL, GRUPO_RECEPCION
from pacientes.models import Paciente
from profesionales.models import Profesional
from turnos.models import Turno

from .models import AdjuntoHistoria


CLAVE = 'ClaveSegura2026!'


def imagen_jpeg_bytes(width=800, height=600, exif=None):
    salida = io.BytesIO()
    kwargs = {'format': 'JPEG'}
    if exif is not None:
        kwargs['exif'] = exif
    Image.new('RGB', (width, height), color=(220, 30, 30)).save(
        salida,
        **kwargs,
    )
    return salida.getvalue()


def imagen_png_bytes(width=120, height=80):
    salida = io.BytesIO()
    Image.new('RGBA', (width, height), color=(0, 120, 220, 128)).save(
        salida,
        format='PNG',
    )
    return salida.getvalue()


def pdf_bytes(contenido=b'Historia clinica de prueba'):
    return b'%PDF-1.4\n' + contenido + b'\n%%EOF\n'


class AdjuntosHistoriaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        grupo_recepcion, _ = Group.objects.get_or_create(name=GRUPO_RECEPCION)
        grupo_profesional, _ = Group.objects.get_or_create(
            name=GRUPO_PROFESIONAL
        )

        cls.recepcion = User.objects.create_user(
            username='recepcion_adjuntos',
            password=CLAVE,
        )
        cls.recepcion.groups.add(grupo_recepcion)

        cls.user_a = User.objects.create_user(
            username='prof_adjuntos_a',
            password=CLAVE,
        )
        cls.user_a.groups.add(grupo_profesional)

        cls.user_b = User.objects.create_user(
            username='prof_adjuntos_b',
            password=CLAVE,
        )
        cls.user_b.groups.add(grupo_profesional)

        cls.prof_a = Profesional.objects.create(
            nombre='Ana',
            apellido='Adjuntos',
            dni='32000001',
            email='ana.adjuntos@example.com',
            fecha_ingreso=date(2020, 1, 15),
            usuario=cls.user_a,
        )
        cls.prof_b = Profesional.objects.create(
            nombre='Bruno',
            apellido='Adjuntos',
            dni='32000002',
            email='bruno.adjuntos@example.com',
            fecha_ingreso=date(2021, 2, 20),
            usuario=cls.user_b,
        )

        cls.p1 = Paciente.objects.create(
            dni='33000001',
            nombre='Paciente',
            apellido='Con adjuntos',
            fecha_nacimiento=date(1985, 4, 12),
        )
        cls.p2 = Paciente.objects.create(
            dni='33000002',
            nombre='Paciente',
            apellido='Ajeno',
            fecha_nacimiento=date(1990, 6, 20),
        )

        cls.fecha_hora = timezone.make_aware(
            timezone.datetime.combine(date.today(), time(10, 0))
        )
        cls.turno_a = Turno.objects.create(
            paciente=cls.p1,
            profesional=cls.prof_a,
            fecha_hora=cls.fecha_hora,
            motivo='Control con historia',
        )
        cls.turno_b = Turno.objects.create(
            paciente=cls.p2,
            profesional=cls.prof_b,
            fecha_hora=cls.fecha_hora,
            motivo='Control ajeno',
        )

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

    def login(self, user):
        self.client.force_login(user)

    def datos_turno(self, motivo='Control con adjuntos'):
        return {
            'paciente': self.p1.pk,
            'profesional': self.prof_a.pk,
            'fecha_hora': self.fecha_hora.strftime('%Y-%m-%dT%H:%M'),
            'motivo': motivo,
            'estado': 'pendiente',
            'observaciones': '',
        }

    def crear_adjunto(
        self,
        paciente=None,
        turno=None,
        nombre='foto.jpg',
        contenido=None,
        content_type='image/jpeg',
        descripcion='',
    ):
        if contenido is None:
            contenido = imagen_jpeg_bytes()
        return AdjuntoHistoria.objects.create(
            paciente=paciente or self.p1,
            turno=turno,
            archivo=SimpleUploadedFile(nombre, contenido, content_type),
            descripcion=descripcion,
            subido_por=self.recepcion,
        )

    def test_formulario_turno_es_multipart_y_permite_multiples_archivos(self):
        self.login(self.recepcion)
        response = self.client.get(reverse('turnos:crear'))

        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'name="adjuntos"')
        self.assertContains(response, 'multiple')
        self.assertContains(
            response,
            'accept="image/jpeg,image/png,application/pdf"',
        )

    def test_turno_guarda_multiples_adjuntos_validos(self):
        self.login(self.recepcion)
        data = self.datos_turno()
        data['adjuntos'] = [
            SimpleUploadedFile('foto.jpg', imagen_jpeg_bytes(), 'image/jpeg'),
            SimpleUploadedFile('estudio.pdf', pdf_bytes(), 'application/pdf'),
        ]

        response = self.client.post(reverse('turnos:crear'), data)

        self.assertEqual(response.status_code, 302)
        turno = Turno.objects.get(motivo='Control con adjuntos')
        adjuntos = AdjuntoHistoria.objects.filter(turno=turno)
        self.assertEqual(adjuntos.count(), 2)
        self.assertEqual(
            set(adjuntos.values_list('paciente_id', flat=True)),
            {self.p1.pk},
        )
        self.assertEqual(
            set(adjuntos.values_list('subido_por_id', flat=True)),
            {self.recepcion.pk},
        )

    def test_turno_rechaza_un_archivo_invalido_sin_guardar_nada(self):
        self.login(self.recepcion)
        data = self.datos_turno('No debe guardarse')
        data['adjuntos'] = [
            SimpleUploadedFile('foto.jpg', imagen_jpeg_bytes(), 'image/jpeg'),
            SimpleUploadedFile('malo.txt', b'texto plano', 'text/plain'),
        ]

        response = self.client.post(reverse('turnos:crear'), data)

        self.assertEqual(response.status_code, 200)
        self.assertIn('adjuntos', response.context['form'].errors)
        self.assertFalse(Turno.objects.filter(motivo='No debe guardarse').exists())
        self.assertEqual(AdjuntoHistoria.objects.count(), 0)

    def test_turno_rechaza_mime_invalido(self):
        self.login(self.recepcion)
        data = self.datos_turno('MIME inválido')
        data['adjuntos'] = SimpleUploadedFile(
            'falso.jpg',
            b'no soy una imagen',
            'image/jpeg',
        )

        response = self.client.post(reverse('turnos:crear'), data)

        self.assertEqual(response.status_code, 200)
        errores = str(response.context['form'].errors['adjuntos'])
        self.assertIn('Tipo de archivo no permitido', errores)
        self.assertFalse(Turno.objects.filter(motivo='MIME inválido').exists())
        self.assertEqual(AdjuntoHistoria.objects.count(), 0)

    def test_turno_rechaza_archivo_mayor_a_10_mb(self):
        self.login(self.recepcion)
        data = self.datos_turno('Archivo gigante')
        contenido = b'%PDF-1.4\n' + b'0' * (10 * 1024 * 1024)
        data['adjuntos'] = SimpleUploadedFile(
            'grande.pdf',
            contenido,
            'application/pdf',
        )

        response = self.client.post(reverse('turnos:crear'), data)

        self.assertEqual(response.status_code, 200)
        errores = str(response.context['form'].errors['adjuntos'])
        self.assertIn('10 MB', errores)
        self.assertFalse(Turno.objects.filter(motivo='Archivo gigante').exists())

    def test_imagen_aplica_orientacion_elimina_exif_y_reduce_tamano(self):
        self.login(self.recepcion)
        exif = Image.Exif()
        exif[0x0112] = 6  # Orientación: rotar 90°
        exif[0x010F] = 'Cámara de prueba'
        exif[0x8825] = {1: 'N', 2: 34.0}  # GPS
        data = self.datos_turno('Turno con EXIF')
        data['adjuntos'] = SimpleUploadedFile(
            'foto_con_exif.jpg',
            imagen_jpeg_bytes(3000, 1000, exif=exif),
            'image/jpeg',
        )

        response = self.client.post(reverse('turnos:crear'), data)

        self.assertEqual(response.status_code, 302)
        adjunto = AdjuntoHistoria.objects.get(turno__motivo='Turno con EXIF')
        with adjunto.archivo.open('rb') as archivo:
            with Image.open(archivo) as imagen:
                self.assertEqual(max(imagen.size), 2000)
                self.assertGreater(imagen.height, imagen.width)
                self.assertEqual(dict(imagen.getexif()), {})

    def test_png_y_pdf_se_conservan(self):
        self.login(self.recepcion)
        data = self.datos_turno('Turno PNG y PDF')
        data['adjuntos'] = [
            SimpleUploadedFile(
                'estudio.png',
                imagen_png_bytes(),
                'image/png',
            ),
            SimpleUploadedFile(
                'receta.pdf',
                pdf_bytes(),
                'application/pdf',
            ),
        ]

        response = self.client.post(reverse('turnos:crear'), data)

        self.assertEqual(response.status_code, 302)
        adjuntos = AdjuntoHistoria.objects.filter(
            turno__motivo='Turno PNG y PDF'
        )
        png = adjuntos.get(archivo__endswith='.png')
        pdf = adjuntos.get(archivo__endswith='.pdf')

        with png.archivo.open('rb') as archivo:
            with Image.open(archivo) as imagen:
                self.assertEqual(imagen.format, 'PNG')
                self.assertEqual(imagen.mode, 'RGBA')

        with pdf.archivo.open('rb') as archivo:
            self.assertTrue(archivo.read().startswith(b'%PDF'))

    def test_paciente_recibe_adjunto_y_profesional_ajeno_no_puede(self):
        self.login(self.recepcion)
        response = self.client.post(
            reverse('historias:subir_adjunto_historia', args=[self.p1.pk]),
            {
                'archivo': SimpleUploadedFile(
                    'estudio.jpg',
                    imagen_jpeg_bytes(),
                    'image/jpeg',
                ),
                'descripcion': 'Estudio de laboratorio',
            },
        )

        self.assertEqual(response.status_code, 302)
        adjunto = AdjuntoHistoria.objects.get()
        self.assertEqual(adjunto.paciente, self.p1)
        self.assertEqual(adjunto.descripcion, 'Estudio de laboratorio')
        self.assertEqual(adjunto.subido_por, self.recepcion)

        self.login(self.user_a)
        response = self.client.post(
            reverse('historias:subir_adjunto_historia', args=[self.p1.pk]),
            {
                'archivo': SimpleUploadedFile(
                    'otro.jpg',
                    imagen_jpeg_bytes(),
                    'image/jpeg',
                ),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AdjuntoHistoria.objects.count(), 2)

        self.login(self.user_b)
        response = self.client.post(
            reverse('historias:subir_adjunto_historia', args=[self.p1.pk]),
            {
                'archivo': SimpleUploadedFile(
                    'ajeno.jpg',
                    imagen_jpeg_bytes(),
                    'image/jpeg',
                ),
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(AdjuntoHistoria.objects.count(), 2)

    def test_solo_recepcion_elimina_y_borra_archivo_del_storage(self):
        adjunto = self.crear_adjunto()
        ruta = adjunto.archivo.path
        self.assertTrue(os.path.exists(ruta))

        self.login(self.user_a)
        response = self.client.post(
            reverse('historias:eliminar_adjunto_historia', args=[adjunto.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(AdjuntoHistoria.objects.filter(pk=adjunto.pk).exists())
        self.assertTrue(os.path.exists(ruta))

        self.login(self.recepcion)
        response = self.client.post(
            reverse('historias:eliminar_adjunto_historia', args=[adjunto.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AdjuntoHistoria.objects.filter(pk=adjunto.pk).exists())
        self.assertFalse(os.path.exists(ruta))

    def test_descarga_imagen_y_pdf_con_headers_seguros_y_auditoria(self):
        imagen = self.crear_adjunto(nombre='foto.jpg')
        pdf = self.crear_adjunto(
            nombre='receta.pdf',
            contenido=pdf_bytes(),
            content_type='application/pdf',
        )
        self.login(self.recepcion)

        response_imagen = self.client.get(
            reverse(
                'historias:descargar_adjunto_historia',
                args=[imagen.pk],
            )
        )
        self.assertEqual(response_imagen.status_code, 200)
        self.assertEqual(
            response_imagen['X-Content-Type-Options'],
            'nosniff',
        )
        self.assertTrue(
            response_imagen['Content-Disposition'].startswith('inline')
        )
        response_imagen.close()

        response_pdf = self.client.get(
            reverse('historias:descargar_adjunto_historia', args=[pdf.pk])
        )
        self.assertEqual(response_pdf.status_code, 200)
        self.assertEqual(response_pdf['X-Content-Type-Options'], 'nosniff')
        self.assertTrue(
            response_pdf['Content-Disposition'].startswith('attachment')
        )
        response_pdf.close()

        self.assertTrue(
            LogAcceso.objects.filter(
                accion='descargar',
                modelo='AdjuntoHistoria',
                objeto_id=imagen.pk,
            ).exists()
        )

    def test_profesional_ajeno_recibe_404_al_descargar(self):
        adjunto = self.crear_adjunto(paciente=self.p1)

        self.login(self.user_a)
        response = self.client.get(
            reverse(
                'historias:descargar_adjunto_historia',
                args=[adjunto.pk],
            )
        )
        self.assertEqual(response.status_code, 200)
        response.close()

        self.login(self.user_b)
        response = self.client.get(
            reverse(
                'historias:descargar_adjunto_historia',
                args=[adjunto.pk],
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_ficha_paciente_lista_adjuntos_y_acciones_por_rol(self):
        adjunto = self.crear_adjunto(descripcion='Estudio de laboratorio')

        self.login(self.recepcion)
        response = self.client.get(
            reverse('pacientes:detalle', args=[self.p1.pk])
        )
        self.assertContains(response, 'Historia clínica adjunta')
        self.assertContains(response, 'Estudio de laboratorio')
        self.assertContains(
            response,
            reverse(
                'historias:descargar_adjunto_historia',
                args=[adjunto.pk],
            ),
        )
        self.assertContains(
            response,
            reverse(
                'historias:eliminar_adjunto_historia',
                args=[adjunto.pk],
            ),
        )
        self.assertContains(
            response,
            reverse(
                'historias:subir_adjunto_historia',
                args=[self.p1.pk],
            ),
        )

        self.login(self.user_a)
        response = self.client.get(
            reverse('pacientes:detalle', args=[self.p1.pk])
        )
        self.assertContains(
            response,
            reverse(
                'historias:descargar_adjunto_historia',
                args=[adjunto.pk],
            ),
        )
        self.assertContains(
            response,
            reverse(
                'historias:subir_adjunto_historia',
                args=[self.p1.pk],
            ),
        )
        self.assertNotContains(
            response,
            reverse(
                'historias:eliminar_adjunto_historia',
                args=[adjunto.pk],
            ),
        )

    def test_agenda_muestra_cantidad_de_adjuntos(self):
        self.crear_adjunto(turno=self.turno_a)
        self.login(self.recepcion)

        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': date.today().isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '📎 1')

    def test_formulario_edicion_lista_adjuntos_existentes(self):
        adjunto = self.crear_adjunto(
            turno=self.turno_a,
            descripcion='Adjunto del turno',
        )
        self.login(self.recepcion)

        response = self.client.get(
            reverse('turnos:editar', args=[self.turno_a.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Adjuntos existentes')
        self.assertContains(response, 'Adjunto del turno')
        self.assertContains(
            response,
            reverse(
                'historias:descargar_adjunto_historia',
                args=[adjunto.pk],
            ),
        )
