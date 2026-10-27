from datetime import date
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from consultorio_salto.context_processors import nombre_centro
from pacientes.models import Paciente


class NombreCentroConfigTests(TestCase):
    def test_setting_nombre_centro(self):
        self.assertEqual(
            settings.NOMBRE_CENTRO,
            'Consultorios Médicos - Salto de las Rosas',
        )
        self.assertEqual(
            settings.NOMBRE_CENTRO_TITULO,
            'Consultorios Médicos',
        )
        self.assertEqual(
            settings.NOMBRE_CENTRO_LOCALIDAD,
            'Salto de las Rosas',
        )

    def test_context_processor_expone_nombre_centro(self):
        self.assertEqual(
            nombre_centro(None),
            {
                'NOMBRE_CENTRO': settings.NOMBRE_CENTRO,
                'NOMBRE_CENTRO_TITULO': settings.NOMBRE_CENTRO_TITULO,
                'NOMBRE_CENTRO_LOCALIDAD': settings.NOMBRE_CENTRO_LOCALIDAD,
            },
        )

    def test_context_processor_registrado_en_templates(self):
        procesadores = settings.TEMPLATES[0]['OPTIONS']['context_processors']
        self.assertIn(
            'consultorio_salto.context_processors.nombre_centro',
            procesadores,
        )


class NombreCentroTemplatesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='recepcion',
            password='clave-segura-123',
        )
        self.user.groups.add(
            Group.objects.get_or_create(name='Recepcion')[0]
        )
        self.client.force_login(self.user)

    def test_login_muestra_nombre_completo(self):
        self.client.logout()
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<title>Iniciar Sesión — {settings.NOMBRE_CENTRO}</title>',
            html=False,
        )
        self.assertContains(
            response,
            f'<h1>{settings.NOMBRE_CENTRO_TITULO}</h1>',
            html=False,
        )
        self.assertContains(
            response,
            f'<p>{settings.NOMBRE_CENTRO_LOCALIDAD}</p>',
            html=False,
        )
        self.assertNotContains(response, 'Centro Médico Integral')

    def test_dashboard_sidebar_footer_y_title(self):
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<title>Dashboard — {settings.NOMBRE_CENTRO}</title>',
            html=False,
        )
        self.assertContains(response, '<div class="brand-name">Consultorios Médicos</div>', html=False)
        self.assertContains(response, '<div class="brand-sub">Salto de las Rosas</div>', html=False)
        self.assertContains(
            response,
            f'<div class="footer-title">{settings.NOMBRE_CENTRO}</div>',
            html=False,
        )
        self.assertNotContains(response, 'Centro Médico Integral')

    def test_detalle_paciente_usa_nombre_completo_en_title(self):
        paciente = Paciente.objects.create(
            dni='30111222',
            nombre='Ana',
            apellido='Pérez',
            fecha_nacimiento=date(1985, 4, 12),
        )
        response = self.client.get(
            reverse('pacientes:detalle', args=[paciente.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<title>{paciente} — {settings.NOMBRE_CENTRO}</title>',
            html=False,
        )

    def test_pdf_usa_nombre_centro_en_el_encabezado(self):
        paciente = Paciente.objects.create(
            dni='28999888',
            nombre='Juan',
            apellido='Gómez',
            fecha_nacimiento=date(1978, 9, 3),
        )

        with patch('pacientes.views.SimpleDocTemplate') as mock_doc, \
                patch('pacientes.views.Paragraph') as mock_paragraph:
            response = self.client.get(
                reverse('pacientes:descargar_pdf', args=[paciente.pk])
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        mock_doc.return_value.build.assert_called_once()
        primer_texto = mock_paragraph.call_args_list[0][0][0]
        self.assertEqual(primer_texto, settings.NOMBRE_CENTRO)
