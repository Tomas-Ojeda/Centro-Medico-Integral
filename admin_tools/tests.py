import io
import shutil
import tempfile
import zipfile
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from auditoria.models import LogAcceso
from consultorio_salto.permisos import GRUPO_PROFESIONAL, GRUPO_RECEPCION


CLAVE = 'ClaveSegura2026!'


class RespaldoAdjuntosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username='admin_respaldo',
            email='admin_respaldo@example.com',
            password=CLAVE,
        )
        cls.recepcion = User.objects.create_user(
            username='recepcion_respaldo',
            password=CLAVE,
        )
        cls.recepcion.groups.add(
            Group.objects.get_or_create(name=GRUPO_RECEPCION)[0]
        )
        cls.profesional = User.objects.create_user(
            username='profesional_respaldo',
            password=CLAVE,
        )
        cls.profesional.groups.add(
            Group.objects.get_or_create(name=GRUPO_PROFESIONAL)[0]
        )

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

    def url(self):
        return reverse('admin_tools:respaldo_adjuntos')

    def test_url_exacta(self):
        self.assertEqual(self.url(), '/admin-tools/respaldo-adjuntos/')

    def test_anonimo_redirige_al_login(self):
        response = self.client.get(self.url())

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_recepcion_recibe_403(self):
        self.client.force_login(self.recepcion)

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            LogAcceso.objects.filter(modelo='RespaldoAdjuntos').exists()
        )

    def test_profesional_recibe_403(self):
        self.client.force_login(self.profesional)

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            LogAcceso.objects.filter(modelo='RespaldoAdjuntos').exists()
        )

    def test_superusuario_descarga_zip_con_adjuntos_y_auditoria(self):
        adjuntos = Path(self.media_root) / 'historias_clinicas'
        adjuntos.mkdir(parents=True)
        (adjuntos / 'estudio.pdf').write_bytes(b'%PDF-1.4 contenido')
        subcarpeta = adjuntos / '2026' / '01'
        subcarpeta.mkdir(parents=True)
        (subcarpeta / 'foto.jpg').write_bytes(b'contenido de imagen')
        (Path(self.media_root) / 'nota.txt').write_bytes(b'otro archivo')

        self.client.force_login(self.admin)
        response = self.client.get(self.url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('.zip', response['Content-Disposition'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

        contenido = b''.join(response.streaming_content)
        response.close()

        with zipfile.ZipFile(io.BytesIO(contenido)) as archivo_zip:
            nombres = set(archivo_zip.namelist())
            self.assertEqual(
                nombres,
                {
                    'historias_clinicas/estudio.pdf',
                    'historias_clinicas/2026/01/foto.jpg',
                    'nota.txt',
                },
            )
            self.assertEqual(
                archivo_zip.read('historias_clinicas/estudio.pdf'),
                b'%PDF-1.4 contenido',
            )
            self.assertEqual(
                archivo_zip.read('historias_clinicas/2026/01/foto.jpg'),
                b'contenido de imagen',
            )

        log = LogAcceso.objects.get(
            accion='descargar',
            modelo='RespaldoAdjuntos',
        )
        self.assertEqual(log.usuario, self.admin)
        self.assertIn('3 archivos', log.detalle)

    def test_media_root_vacio_genera_zip_valido(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url())

        self.assertEqual(response.status_code, 200)
        contenido = b''.join(response.streaming_content)
        response.close()

        with zipfile.ZipFile(io.BytesIO(contenido)) as archivo_zip:
            self.assertEqual(archivo_zip.namelist(), [])

        log = LogAcceso.objects.get(
            accion='descargar',
            modelo='RespaldoAdjuntos',
        )
        self.assertIn('0 archivos', log.detalle)
